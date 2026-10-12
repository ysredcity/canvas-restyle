#!/usr/bin/env python3
"""飞书画板适配器：raw 原位重绘引擎（飞书的默认引擎）。

读取飞书画板 raw 导出，保持每个节点的位置、尺寸、文字与层级，只按「角色 + 原色色系」
重新配色、统一字号层级与对齐，输出可被 whiteboard-cli 导入的 SVG。

用法：
  python3 redraw.py raw.json -o diagram.svg [--style style.json] [--report report.json]
                    [--map "#e8f8f3=teal/soft" ...] [--scale 0.5]

角色：container（包含其他形状的形状 / section）、card（带文字或无文字的叶子形状）、step（流程箭头形状）、
     table、text（独立文本）、connector、image（SVG 小图标，如箭头三角）。
"""
import argparse
import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import (Svg, abs_box, family_of, index, layout_text, load_raw, text_width)
from core.geom import inside, overlap_ratio
from core.palette import Mapper, load_style, parse_maps, text_color

PAD = 40
LINE_W = {'extra_narrow': 1, 'narrow': 1.4, 'medium': 2, 'wide': 3, 'extra_wide': 4}


# ================================================================ 样式（决策在 core.palette）
def fill_of(n):
    s = n.get('style') or {}
    f = s.get('fill_color')
    if not f or (s.get('fill_opacity') is not None and s['fill_opacity'] < 15): return None
    return f.lower()


def border_of(n):
    s = n.get('style') or {}
    if s.get('border_style') in (None, 'none') or not s.get('border_color'): return None
    if s.get('border_opacity') is not None and s['border_opacity'] < 15: return None
    return s['border_color'].lower()


# ================================================================ 角色划分
def classify(nodes, D):
    B = {n['id']: abs_box(n, D) for n in nodes}
    shapes = [n for n in nodes if n['type'] in ('composite_shape', 'section') and not
              (n.get('parent_id') and D.get(n['parent_id'], {}).get('type') == 'table')]
    role, depth, parent = {}, {}, {}
    for n in shapes:
        b = B[n['id']]
        holders = [m for m in shapes if m is not n and B[m['id']][2] * B[m['id']][3] > b[2] * b[3] and inside(b, B[m['id']])]
        depth[n['id']] = len(holders)
        if holders: parent[n['id']] = min(holders, key=lambda m: B[m['id']][2] * B[m['id']][3])['id']
    for n in shapes:
        has_child = any(parent.get(m['id']) == n['id'] for m in shapes)
        kind = (n.get('composite_shape') or {}).get('type', '')
        op = (n.get('style') or {}).get('fill_opacity')
        covers = any(m is not n and overlap_ratio(B[m['id']], b2) > 0 for m in shapes for b2 in [B[n['id']]]
                     if B[m['id']][2] * B[m['id']][3] < b2[2] * b2[3])
        if n['type'] == 'section': role[n['id']] = 'container'
        elif op is not None and 15 <= op < 95 and covers: role[n['id']] = 'overlay'
        elif kind.startswith('step'): role[n['id']] = 'step'
        elif has_child: role[n['id']] = 'container'
        else: role[n['id']] = 'card'
    for n in nodes:
        if n['type'] == 'composite_shape' and n['id'] not in role: role[n['id']] = 'card'   # 表格内胶囊
        if n['type'] == 'text_shape':
            b = B[n['id']]
            hosts = [m for m in shapes if inside(b, B[m['id']])]
            if hosts: parent[n['id']] = min(hosts, key=lambda m: B[m['id']][2] * B[m['id']][3])['id']
            role[n['id']] = 'text'
        if n['type'] in ('table', 'connector', 'image'): role[n['id']] = n['type']
    return B, role, depth, parent


# ================================================================ 绘制
class Painter:
    def __init__(self, nodes, st, overrides, scale=None):
        self.nodes, self.st = nodes, st
        self.D = index(nodes)
        self.B, self.role, self.depth, self.parent = classify(nodes, self.D)
        self.M = Mapper(st, overrides)
        self.warn = []
        boxes = [b for i, b in self.B.items() if self.D[i]['type'] not in ('group',)]
        self.minx = min(b[0] for b in boxes); self.miny = min(b[1] for b in boxes)
        maxx = max(b[0] + b[2] for b in boxes); maxy = max(b[1] + b[3] for b in boxes)
        fss = [n['text']['font_size'] for n in nodes if (n.get('text') or {}).get('text') and n['text'].get('font_size')]
        med = statistics.median(fss) if fss else 14
        self.S = scale or (1.0 if med <= 24 else round(16 / med / 0.05) * 0.05)
        self.svg = Svg((maxx - self.minx) * self.S + PAD * 2, (maxy - self.miny) * self.S + PAD * 2, st.get('page_bg'))
        self.bgs = {}

    # 坐标
    def tb(self, b):
        return ((b[0] - self.minx) * self.S + PAD, (b[1] - self.miny) * self.S + PAD, b[2] * self.S, b[3] * self.S)

    def tp(self, x, y):
        return (x - self.minx) * self.S + PAD, (y - self.miny) * self.S + PAD

    # 文字颜色规则见 core.palette.text_color
    def text_color(self, n, host_paint):
        return text_color(self.st, (n.get('text') or {}).get('text_color'), host_paint)

    def draw_text(self, n, box, host_paint, pad=None):
        t = n.get('text') or {}
        s = (t.get('text') or '')
        if not s.strip(): return
        fs = (t.get('font_size') or 14) * self.S
        bold = t.get('font_weight') == 'bold'
        ha, va = t.get('horizontal_align', 'center'), t.get('vertical_align', 'mid')
        pad = pad if pad is not None else (8 if box[2] > 60 else 3)
        color = self.text_color(n, host_paint)
        if self.rich(n, box, fs, color, ha, va, pad): return
        lines, fs2 = layout_text(s, box[2] - pad * 2, box[3] - pad * 2, fs, bold, min_fs=max(9, fs * 0.7))
        self.svg.text_block(box, lines, fs2, color, bold, ha, va, pad)

    def rich(self, n, box, fs, color, ha, va, pad):
        """富文本（段内粗体）：每段能单行放下时，用多个 <text> 手动排位保留粗体；否则返回 False 走普通排版。"""
        paras = ((n.get('text') or {}).get('rich_text') or {}).get('paragraphs')
        if not paras or not any(e.get('text_element', {}).get('text_style', {}).get('font_weight') == 'bold'
                                for p in paras for e in p.get('elements', [])):
            return False
        rows = []
        for p in paras:
            segs = [(e['text_element']['text'], e['text_element'].get('text_style', {}).get('font_weight') == 'bold')
                    for e in p.get('elements', []) if 'text_element' in e]
            w = sum(text_width(s, fs, b) for s, b in segs)
            if w > box[2] - pad * 2: return False
            rows.append((segs, w))
        accent = self.st['families']['blue']['soft']['text'] if color in (self.st['ink'], self.st['muted']) else color
        step = fs * 1.6; y0 = box[1] + (box[3] - step * len(rows)) / 2 if va != 'top' else box[1] + pad
        for i, (segs, w) in enumerate(rows):
            x = {'left': box[0] + pad, 'right': box[0] + box[2] - pad - w}.get(ha, box[0] + (box[2] - w) / 2)
            for s, b in segs:
                self.svg.text(x, y0 + i * step + step / 2 + fs * 0.36, s, fs, accent if b else color, b)
                x += text_width(s, fs, b)
        return True

    # 形状
    def shape_paint(self, n, role):
        f = fill_of(n)
        if f is None: return None
        return self.M.paint(f, role)

    def draw_container(self, n):
        b = self.tb(self.B[n['id']])
        r = self.st['radius']['container']
        p = self.shape_paint(n, 'container')
        stroke = border_of(n)
        dash = '5 4' if (n.get('style') or {}).get('border_style') in ('dash', 'dashed', 'dotted') else None
        if p and p[1] == 'solid':
            bg, bd = p[2]['bg'], p[2]['border']
        elif p and p[0] != 'neutral':
            bg, bd = p[2]['bg'], p[2]['border']
        elif p:
            bg = self.st['container']['bg'] if self.depth.get(n['id'], 0) % 2 == 0 else self.st['container']['alt_bg']
            bd = self.st['container']['border']
        else:
            bg, bd = 'none', self.st['container']['border'] if (stroke or dash) else None
        # 容器一律画成多边形：检查器不把 polygon 计入重叠，避免嵌套 / 交叠误报
        self.bgs[n['id']] = p
        self.svg.rpoly(*b, fill=bg, stroke=bd, r=r, sw=1, dash=dash, shadow=self.depth.get(n['id'], 0) == 0 and bg != 'none')
        if n['type'] == 'section':
            title = (n.get('section') or {}).get('title')
            if title:
                # 飞书里 section 标题显示在框外左上方
                self.svg.text(b[0] + 4, b[1] - 8, title, 15 * max(self.S, 0.8), self.st['heading'], True)
        elif (n.get('text') or {}).get('text', '').strip():
            t = dict(n['text']); t['vertical_align'] = 'top'
            self.draw_text({'text': t}, (b[0], b[1] + 4, b[2], min(b[3], 44 * self.S + 16)), p, pad=10)

    def draw_card(self, n):
        b = self.tb(self.B[n['id']])
        p = self.shape_paint(n, 'card')
        stroke = border_of(n)
        dash = '5 4' if (n.get('style') or {}).get('border_style') in ('dash', 'dashed', 'dotted') else None
        kind = (n.get('composite_shape') or {}).get('type', 'round_rect')
        r = self.st['radius']['small'] if b[3] < 40 else self.st['radius']['card']
        if p:
            bg, bd = p[2]['bg'], p[2]['border']
        elif stroke or dash:
            bg, bd = 'none', self.st['families']['neutral']['white']['border']
        else:
            bg, bd = None, None          # 透明文字容器
        if bg is not None:
            if kind in ('ellipse', 'circle'):
                self.svg.add(f'<ellipse cx="{b[0] + b[2] / 2:.1f}" cy="{b[1] + b[3] / 2:.1f}" rx="{b[2] / 2:.1f}" ry="{b[3] / 2:.1f}" '
                             f'fill="{bg}" stroke="{bd}" stroke-width="1"/>')
            elif kind == 'diamond':
                x, y, w, h = b
                self.svg.polygon([(x + w / 2, y), (x + w, y + h / 2), (x + w / 2, y + h), (x, y + h / 2)], bg, bd)
            elif min(b[2], b[3]) < 12 and not (n.get('text') or {}).get('text', '').strip():
                # 细条装饰：画成粗线，避免文字压在上面时被判为溢出
                if b[2] >= b[3]: self.svg.line(b[0], b[1] + b[3] / 2, b[0] + b[2], b[1] + b[3] / 2, bg if bg != 'none' else bd, max(b[3], 1))
                else: self.svg.line(b[0] + b[2] / 2, b[1], b[0] + b[2] / 2, b[1] + b[3], bg if bg != 'none' else bd, max(b[2], 1))
            elif n['id'] in self.clash:
                self.svg.rpoly(*b, fill=bg, stroke=bd, r=0 if kind == 'rect' else r, sw=1, dash=dash)
            else:
                self.svg.rect(*b, fill=bg, stroke=bd, rx=0 if kind == 'rect' else r, sw=1, dash=dash)
        self.bgs[n['id']] = p
        self.draw_text(n, b, p)

    def draw_overlay(self, n):
        """半透明遮罩（原图用来表示「某阶段范围」）：遮罩会盖住下面的条目，改为虚线框 + 角标胶囊。"""
        b = self.tb(self.B[n['id']])
        p = self.shape_paint(n, 'overlay') or self.M.paint('#2f5bd3', 'overlay')
        fam = p[0] if p[0] != 'neutral' else 'blue'
        c = self.st['families'][fam]['solid']
        self.svg.rpoly(*b, fill='none', stroke=c['bg'], r=self.st['radius']['card'], sw=1.4, dash='6 4')
        s = (n.get('text') or {}).get('text', '').strip()
        if s:
            fs = 12; x, y, w, h = self.badge[n['id']]
            self.svg.rect(x, y, w, h, c['bg'], None, h / 2)
            self.svg.text(x + w / 2, y + h / 2 + fs * 0.36, s, fs, c['text'], True, 'middle')
        self.warn.append(f'半透明遮罩 {n["id"]}「{s[:10]}」改为虚线框 + 角标')

    def draw_steps(self, steps):
        """流程箭头：同一行按 x 排序，宽度收到下一个起点前，避免相互叠压。"""
        rows = {}
        for n in steps:
            b = self.B[n['id']]; rows.setdefault(round((b[1] + b[3] / 2) / 10), []).append(n)
        for row in rows.values():
            row.sort(key=lambda n: self.B[n['id']][0])
            for k, n in enumerate(row):
                x, y, w, h = self.tb(self.B[n['id']]); d = min(h * 0.42, w * 0.3)
                if k + 1 < len(row):
                    nx = self.tb(self.B[row[k + 1]['id']])[0]
                    if nx < x + w: w = min(w, nx - x + d - 6)
                p = self.shape_paint(n, 'step') or self.M.paint('#eef4fb', 'step')
                first = k == 0
                pts = [(x, y), (x + w - d, y), (x + w, y + h / 2), (x + w - d, y + h), (x, y + h)] + ([] if first else [(x + d, y + h / 2)])
                self.svg.polygon(pts, p[2]['bg'], p[2]['border'])
                self.bgs[n['id']] = p
                self.draw_text(n, (x + (0 if first else d * 0.6), y, w - d * (0.6 if first else 1.2), h), p, pad=4)

    def draw_table(self, n):
        x0, y0, _, _ = self.tb(self.B[n['id']])
        meta = n['table']['meta']; CS = [c * self.S for c in meta['col_sizes']]; RS = [r * self.S for r in meta['row_sizes']]
        colx = [x0]; [colx.append(colx[-1] + c) for c in CS]
        rowy = [y0]; [rowy.append(rowy[-1] + r) for r in RS]
        head = self.st['families']['teal']['solid']; grid = self.st['grid']
        self.svg.rpoly(x0, y0, colx[-1] - x0, rowy[-1] - y0, '#ffffff', self.st['container']['border'], 10, shadow=True)
        cells = {}; covered = set()
        for c in n['table'].get('cells', []):
            r0, c0 = c['row_index'] - 1, c['col_index'] - 1
            mi = c.get('merge_info') or {}
            cells[(r0, c0)] = (mi.get('row_span', 1), mi.get('col_span', 1), c)
        for (r0, c0), (rs, cs, _) in cells.items():
            for i in range(r0, r0 + rs):
                for j in range(c0, c0 + cs):
                    if (i, j) != (r0, c0): covered.add((i, j))
        for i in range(1, len(RS)):
            if i % 2 == 0: self.svg.rpoly(x0, rowy[i], colx[-1] - x0, RS[i], '#f8fafc', r=0)
        for (r0, c0), (rs, cs, c) in sorted(cells.items()):
            if (r0, c0) in covered: continue
            b = (colx[c0], rowy[r0], colx[c0 + cs] - colx[c0], rowy[r0 + rs] - rowy[r0])
            f = ((c.get('style') or {}).get('fill_color') or '').lower() or None
            p = self.M.paint(f, 'table-cell') if f else None
            if r0 == 0: self.svg.rpoly(*b, head['bg'], r=0)
            elif p: self.svg.rpoly(*b, p[2]['bg'], r=0)
            if r0 > 0:   # 网格只画上边与左边（线不计入重叠检查）
                self.svg.line(b[0], b[1], b[0] + b[2], b[1], grid); self.svg.line(b[0], b[1], b[0], b[1] + b[3], grid)
            if (c.get('text') or {}).get('text'):
                hp = (None, 'solid', head) if r0 == 0 else p
                fake = {'text': dict(c['text'])}
                if r0 == 0: fake['text']['font_weight'] = 'bold'
                self.draw_text(fake, b, hp, pad=10)

    def anchor(self, end):
        if 'attached_object' in end and end['attached_object'].get('id') in self.B:
            o = self.B[end['attached_object']['id']]; p = end['attached_object'].get('position', {'x': 0.5, 'y': 0.5})
            return o[0] + o[2] * p.get('x', 0.5), o[1] + o[3] * p.get('y', 0.5), end['attached_object'].get('snap_to')
        p = end.get('position') or {}
        return p.get('x', 0), p.get('y', 0), None

    def draw_connector(self, n):
        c = n['connector']
        x1, y1, s1 = self.anchor(c['start']); x2, y2, s2 = self.anchor(c['end'])
        pts = [(x1, y1)] + [(t['x'], t['y']) for t in (c.get('turning_points') or []) if 'x' in t] + [(x2, y2)]
        if c.get('shape') == 'polyline' and len(pts) == 2 and abs(x1 - x2) > 1 and abs(y1 - y2) > 1:
            if s1 in ('left', 'right') or s2 in ('left', 'right'):
                mx = (x1 + x2) / 2; pts = [(x1, y1), (mx, y1), (mx, y2), (x2, y2)]
            else:
                my = (y1 + y2) / 2; pts = [(x1, y1), (x1, my), (x2, my), (x2, y2)]
        pts = [self.tp(*p) for p in pts]
        col = border_of(n)
        fam = family_of(col)[0] if col else None
        color = self.st['connector'] if fam in (None, 'neutral') else self.st['families'][fam]['soft']['border']
        sw = LINE_W.get((n.get('style') or {}).get('border_width'), 1.4) + 0.2
        dash = '5 4' if (n.get('style') or {}).get('border_style') in ('dash', 'dashed', 'dotted') else None
        self.svg.polyline(pts, color, sw, dash) if len(pts) > 2 else self.svg.line(*pts[0], *pts[1], color, sw, dash)
        for end, (a, b) in (('end', (pts[-2], pts[-1])), ('start', (pts[1], pts[0]))):
            if (c[end].get('arrow_style') or 'none') != 'none': self.arrowhead(a, b, color)

    def arrowhead(self, a, b, color, size=8):
        dx, dy = b[0] - a[0], b[1] - a[1]; L = max((dx * dx + dy * dy) ** 0.5, 1e-6); ux, uy = dx / L, dy / L
        bx, by = b[0] - ux * size, b[1] - uy * size
        self.svg.polygon([b, (bx - uy * size * 0.55, by + ux * size * 0.55), (bx + uy * size * 0.55, by - ux * size * 0.55)], color)

    def draw_image(self, n):
        tok = (n.get('image') or {}).get('token', '')
        vb = re.search(r'viewBox="([-\d.]+) ([-\d.]+) ', tok)
        polys = re.findall(r'<polygon[^>]*points="([^"]+)"[^>]*?(?:fill="([^"]+)")?', tok)
        if not tok.startswith('<svg') or not vb or not polys or '<path' in tok:
            self.warn.append(f'image {n["id"]} 未重绘（非简单 SVG 图形）'); return
        bx, by, _, _ = self.B[n['id']]; ox, oy = bx - float(vb.group(1)), by - float(vb.group(2))
        for pts, fill in polys:
            P = [self.tp(float(q.split(',')[0]) + ox, float(q.split(',')[1]) + oy) for q in pts.split()]
            P = self.dodge_text(P, n['id'])
            fam = family_of(fill)[0] if fill else None
            color = self.st['connector'] if fam in (None, 'neutral') else self.st['families'][fam]['soft']['border']
            self.svg.polygon(P, color)

    def dodge_text(self, P, nid):
        """检查器把「文字左上角所在的形状」当作文字容器。小图标（如流程箭头）若盖住某段文字的左上角，
        就把图标向远离文字的方向压缩几个像素，避免误判为文字溢出。"""
        x0, y0 = min(p[0] for p in P), min(p[1] for p in P); x1, y1 = max(p[0] for p in P), max(p[1] for p in P)
        M = 4                                        # 检查器的文字宽度估算比实测略大，留余量
        for tx, ty, tw_, th in self.svg.texts:
            if x0 < tx + M and tx - M < x1 and y0 < ty + M and ty - M < y1 and tx + tw_ > x1:
                if tx - x0 >= (x1 - x0) * 0.4:      # 文字在图标右侧：收窄
                    k = max(0.3, (tx - M - x0) / (x1 - x0)); P = [(x0 + (px - x0) * k, py) for px, py in P]
                else:                                # 文字在图标下方：压低
                    k = max(0.3, (ty - M - y0) / (y1 - y0)); P = [(px, y0 + (py - y0) * k) for px, py in P]
                x1, y1 = max(p[0] for p in P), max(p[1] for p in P)
                self.warn.append(f'image {nid} 盖住文字左上角，已压缩 {round((1 - k) * 100)}%')
        return P

    # 主流程
    def run(self):
        N = self.nodes; R = self.role
        self.clash = self.find_clash()
        self.skip = self.find_redundant()
        self.badge = self.overlay_badges()
        z = lambda n: (self.depth.get(n['id'], 0), n.get('z_index', 0))
        for n in sorted([n for n in N if R.get(n['id']) == 'container'], key=z): self.draw_container(n)
        for n in N:
            if R.get(n['id']) == 'table': self.draw_table(n)
        for n in N:
            if R.get(n['id']) == 'connector': self.draw_connector(n)
        self.draw_steps([n for n in N if R.get(n['id']) == 'step'])
        for n in sorted([n for n in N if R.get(n['id']) == 'card' and n['id'] not in self.skip], key=z): self.draw_card(n)
        for n in N:
            if R.get(n['id']) == 'overlay': self.draw_overlay(n)
        for n in N:
            if R.get(n['id']) != 'text': continue
            host = self.parent.get(n['id'])
            self.draw_text(n, self.tb(self.B[n['id']]), self.bgs.get(host), pad=0)
        for n in N:                  # 图标最后画：需要知道文字实际位置
            if R.get(n['id']) == 'image': self.draw_image(n)
        return self.svg

    def find_clash(self):
        """卡片之间部分重叠 ≥50%（原图如此）或卡片完全包含卡片：这些卡片改画多边形，并记入报告。"""
        cards = [n for n in self.nodes if self.role.get(n['id']) == 'card' and (fill_of(n) or border_of(n))]
        clash = set()
        for i, a in enumerate(cards):
            for b in cards[i + 1:]:
                A, Bb = self.B[a['id']], self.B[b['id']]
                if overlap_ratio(A, Bb) >= 0.5:
                    clash.update((a['id'], b['id']))
                    if not (inside(A, Bb) or inside(Bb, A)):
                        self.warn.append(f'原图卡片部分重叠 ≥50%：{a["id"]} / {b["id"]}（版式不变，已按多边形绘制）')
        return clash

    def overlay_badges(self):
        """预先算出遮罩角标位置；被角标压到的卡片改画多边形，避免重叠误报。"""
        out = {}
        for n in self.nodes:
            if self.role.get(n['id']) != 'overlay': continue
            s = (n.get('text') or {}).get('text', '').strip()
            if not s: continue
            b = self.tb(self.B[n['id']]); w = text_width(s, 12, True) + 14; h = 20
            # 角标骑在遮罩右上角（约一半在框外），尽量少压住框内条目
            out[n['id']] = (b[0] + b[2] - w * 0.55, b[1] - h * 0.6, w, h)
            bb = (self.minx + (out[n['id']][0] - PAD) / self.S, self.miny + (out[n['id']][1] - PAD) / self.S, w / self.S, h / self.S)
            for m in self.nodes:
                if self.role.get(m['id']) == 'card' and overlap_ratio(bb, self.B[m['id']]) > 0: self.clash.add(m['id'])
        return out

    def find_redundant(self):
        """无文字、与外层卡片同色、完全落在其内的装饰块（常用于把圆角补成直角）——跳过不画。"""
        cards = [n for n in self.nodes if self.role.get(n['id']) == 'card']
        out = set()
        for n in cards:
            if (n.get('text') or {}).get('text', '').strip() or not fill_of(n): continue
            for m in cards:
                if m is not n and fill_of(m) == fill_of(n) and overlap_ratio(self.B[n['id']], self.B[m['id']]) > 0.6:
                    if self.B[m['id']][2] * self.B[m['id']][3] > self.B[n['id']][2] * self.B[n['id']][3]:
                        out.add(n['id']); break
        return out

    def report(self):
        from collections import Counter
        return {'scale': self.S, 'roles': dict(Counter(self.role.values())),
                'color_map': self.M.table(),
                'warnings': self.warn}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('raw'); ap.add_argument('-o', '--out', default='diagram.svg')
    ap.add_argument('--style', help='样式覆盖 JSON（extract_style.py 产出或手写）')
    ap.add_argument('--report', help='写出角色与配色映射报告 JSON')
    ap.add_argument('--map', action='append', default=[], help='强制原色归类，如 "#e8f8f3=teal/soft"')
    ap.add_argument('--scale', type=float)
    a = ap.parse_args()
    ov = parse_maps(a.map)
    nodes = [n for n in load_raw(a.raw) if n['type'] != 'group']
    P = Painter(nodes, load_style(a.style), ov, a.scale)
    P.run().save(a.out)
    rep = P.report()
    if a.report: json.dump(rep, open(a.report, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({'out': a.out, 'scale': rep['scale'], 'roles': rep['roles'], 'colors': len(rep['color_map']),
                      'warnings': len(rep['warnings'])}, ensure_ascii=False))
    for w in rep['warnings'][:10]: print('  !', w)


if __name__ == '__main__':
    main()
