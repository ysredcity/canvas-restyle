#!/usr/bin/env python3
"""飞书画板适配器：raw 原位重绘引擎（飞书的默认引擎）。

读取飞书画板 raw 导出，保持文字、元素数量、包含关系与阅读顺序，重新配色并规整排版，
输出可被 whiteboard-cli 导入的 SVG。

三档（--mode）：
  conservative  只改配色，坐标/尺寸/字号与原图一致（0.2.x 行为）
  standard（默认）加上对齐吸附、行列等距、同组统一尺寸、字号分档（3–4 档）、统一字体与最小内边距
  aggressive    再加「文字放不下时撑高整行」

用法：
  python3 redraw.py raw.json -o diagram.svg [--mode standard] [--font 微软雅黑] [--style style.json]
                    [--report report.json] [--map "#e8f8f3=teal/soft" ...] [--scale 0.5]

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
from lib import (Svg, abs_box, family_of, hex2rgb, index, layout_text, load_raw, rich_lines, text_width)
from core.color import mix
import core.text as core_text
from core.geom import inside, overlap_ratio
from core.layout import normalize, rows_of, structure_ok
from core.palette import Mapper, load_style, parse_maps, text_color
from core.typography import pick_font, report as fs_report, tier_sizes

PAD = 40
LINE_W = {'extra_narrow': 1, 'narrow': 1.4, 'medium': 2, 'wide': 3, 'extra_wide': 4}


# ================================================================ 样式（决策在 core.palette）
def fill_of(n):
    """填充色。半透明填充（< 95%）按「叠在白底上的观感色」取色：37% 的 #00aaa9 看上去是浅青，不是深青。"""
    s = n.get('style') or {}
    f = s.get('fill_color')
    op = s.get('fill_opacity')
    if not f or (op is not None and op < 15): return None
    f = f.lower()
    if op is not None and op < 95 and hex2rgb(f):
        f = mix(f, '#ffffff', 1 - op / 100)
    return f


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
        b2 = B[n['id']]
        under = [m for m in shapes if m is not n and overlap_ratio(B[m['id']], b2) > 0 and B[m['id']][2] * B[m['id']][3] < b2[2] * b2[3]]
        # 遮罩 = 半透明且「压在」被覆盖形状之上（z 更高）。半透明但垫在下面的只是浅色容器底，不是遮罩。
        z = n.get('z_index', 0)
        covers = bool(under) and sum(1 for m in under if z > m.get('z_index', 0)) * 2 >= len(under)
        if n['type'] == 'section': role[n['id']] = 'container'
        elif kind.startswith('step'): role[n['id']] = 'step'
        elif op is not None and 15 <= op < 95 and covers: role[n['id']] = 'overlay'
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
SHAPE_ROLES = ('card', 'container', 'step', 'overlay')
MIN_PAD = 10            # 文字与容器边缘的最小间距（标准档）
MAX_SHRINK = 0.10       # 标准档：分档字号最多缩 10%，再放不下就撑高整行


class Painter:
    def __init__(self, nodes, st, overrides, scale=None, mode='standard', font=None, tiers=4):
        self.nodes, self.st = nodes, st
        self.D = index(nodes)
        self.B, self.role, self.depth, self.parent = classify(nodes, self.D)
        self.M = Mapper(st, overrides)
        self.warn = []
        self.mode = mode
        core_text.STRICT = mode != 'conservative'      # 换行按检查器口径，避免 text-overflow 误报
        self.layout_info = {}
        self.FS = {}
        self.font = pick_font(font) if (font or mode != 'conservative') else Svg.FONT
        if mode != 'conservative':
            self.FS = self.tier_fonts(tiers)
            self.relayout()
        boxes = [b for i, b in self.B.items() if self.D[i]['type'] not in ('group',)]
        self.minx = min(b[0] for b in boxes); self.miny = min(b[1] for b in boxes)
        maxx = max(b[0] + b[2] for b in boxes); maxy = max(b[1] + b[3] for b in boxes)
        fss = [n['text']['font_size'] for n in nodes if (n.get('text') or {}).get('text') and n['text'].get('font_size')]
        med = statistics.median(fss) if fss else 14
        self.S = scale or (1.0 if med <= 24 else round(16 / med / 0.05) * 0.05)
        self.svg_args = ((maxx - self.minx) * self.S + PAD * 2, (maxy - self.miny) * self.S + PAD * 2, st.get('page_bg'))
        self.svg = Svg(*self.svg_args)
        self.svg.FONT = self.font
        self.fit, self.force = {}, {}       # 标准档两遍绘制：第一遍测每个节点放得下的字号，第二遍同行同档统一
        self.bgs = {}

    # ---------------------------------------------------------------- 排版规整（标准档起）
    def all_sizes(self):
        out = []
        for n in self.nodes:
            t = n.get('text') or {}
            if not (t.get('text') or '').strip(): continue
            out.append(t.get('font_size') or 14)
            for p in ((t.get('rich_text') or {}).get('paragraphs') or []):
                for e in p.get('elements', []):
                    s = (e.get('text_element', {}).get('text_style') or {}).get('font_size')
                    if s: out.append(s)
        return out

    def tier_fonts(self, tiers):
        sizes = self.all_sizes()
        m = tier_sizes(sizes, max_tiers=tiers)
        self.layout_info['font_tiers'] = fs_report(m, sizes)
        return m

    def fs_of(self, size, box=None, text=None, bold=False, pad=0):
        """字号分档后的字号。只有放得下时才上调，避免把文字挤出窄容器。"""
        ts = self.FS.get(size, size)
        if ts > size and box and text:
            lines, _ = layout_text(text, box[2] - pad * 2, 1e6, ts, bold, min_fs=ts)
            if len(lines) * ts * 1.4 + pad * 2 > box[3] + 1: return size
        return ts

    def relayout(self):
        """按父容器分组做对齐 / 等距 / 统一尺寸，再按文字需要撑高行。结构有变化就整组回退。"""
        groups = {}
        ov_old = {n['id']: self.B[n['id']] for n in self.nodes if self.role.get(n['id']) == 'overlay'}
        before = dict(self.B)
        for n in self.nodes:
            # 容器（包含其他形状的形状 / section）不参与规整：它的尺寸由内容决定，规整完子元素后再按需撑开
            if self.role.get(n['id']) in ('card', 'step'):
                groups.setdefault(self.parent.get(n['id']), []).append(n['id'])
        info, applied = [], []
        for p, ids in groups.items():
            if len(ids) < 2: continue
            old = {k: list(self.B[k]) for k in ids}
            new, meta = normalize(old)
            self.keep_covering(old, new)
            iss = structure_ok(old, new, meta['rows'])
            if iss:
                self.warn.append(f'排版规整已回退（父={p or "顶层"}）：{iss[0]}'); continue
            self.apply_boxes(old, new)
            applied.append((p, old, new))
            info.append({'parent': p, 'moved': meta['moved'], 'max_shift': meta['max_shift'],
                         'gap': meta['gap'], 'vgap': meta['vgap']})
        self.revert_cross_overlaps(applied, before, info)
        self.refit_overlays(ov_old, before)
        self.cover_children()
        info.append({'grow_rows': self.grow_rows(0.0 if self.mode == 'aggressive' else 0.05)})
        info.append({'widened_text': self.widen_free_text()})
        self.layout_info['layout'] = info

    def revert_cross_overlaps(self, applied, before, info):
        """不同父容器的卡片之间若出现原图没有的重叠，回退涉及的组（可能要回退多轮）。"""
        cards = [k for k in before if self.role.get(k) in ('card', 'step')]
        def ov(a, b): return overlap_ratio(a, b) > 0.02
        for _ in range(5):
            bad = set()
            for i, a in enumerate(cards):
                for b in cards[i + 1:]:
                    if ov(self.B[a], self.B[b]) and not ov(before[a], before[b]):
                        bad.update((self.parent.get(a), self.parent.get(b)))
            hit = [g for g in applied if g[0] in bad]
            if not hit: return
            for p, old, new in hit:
                self.apply_boxes(new, old); applied.remove((p, old, new))
                self.warn.append(f'排版规整已回退（父={p or "顶层"}）：与相邻分组产生新的重叠')
                for d in info:
                    if d.get('parent') == p: d['reverted'] = True

    def cover_children(self):
        """自内向外：容器至少要包住子元素（保留原有的内边距，至少 MIN_PAD）。"""
        conts = [n['id'] for n in self.nodes if self.role.get(n['id']) == 'container']
        for c in sorted(conts, key=lambda k: -self.depth.get(k, 0)):
            kids = [k for k, p in self.parent.items() if p == c and k in self.B and self.role.get(k) in SHAPE_ROLES]
            if not kids: continue
            x, y, w, h = self.B[c]
            r = max(self.B[k][0] + self.B[k][2] for k in kids) + MIN_PAD
            b = max(self.B[k][1] + self.B[k][3] for k in kids) + MIN_PAD
            self.B[c] = (x, y, max(w, r - x), max(h, b - y))

    def refit_overlays(self, ov_old, before):
        """遮罩（表示「某阶段范围」的虚线框）按它原来框住的那些卡片的新外接框重算，保持原有外扩边距。"""
        for oid, ob in ov_old.items():
            inner = [k for k, b in before.items() if k != oid and self.role.get(k) == 'card' and overlap_ratio(b, ob) >= 0.6]
            if not inner: continue
            def ext(B): return (min(B[k][0] for k in inner), min(B[k][1] for k in inner),
                                max(B[k][0] + B[k][2] for k in inner), max(B[k][1] + B[k][3] for k in inner))
            o0, o1 = ext(before), ext(self.B)
            l, t, r, b = ob[0] - o0[0], ob[1] - o0[1], (ob[0] + ob[2]) - o0[2], (ob[1] + ob[3]) - o0[3]
            self.B[oid] = (o1[0] + l, o1[1] + t, (o1[2] + r) - (o1[0] + l), (o1[3] + b) - (o1[1] + t))

    def keep_covering(self, old, new):
        """形状不能缩到装不住原本落在它里面的独立文字：按需把右/下边补回来。"""
        for n in self.nodes:
            if self.role.get(n['id']) != 'text': continue
            tx, ty, tw, th = self.B[n['id']]
            h = self.parent.get(n['id'])
            if h not in new:      # 没有「完全包住」的宿主时，按检查器的规则取「文字左上角所在的最小形状」（留 4px 容差）
                T = 4
                cand = [k for k in new if old[k][0] - T <= tx <= old[k][0] + old[k][2] + T
                        and old[k][1] - T <= ty <= old[k][1] + old[k][3] + T]
                if not cand: continue
                h = min(cand, key=lambda k: old[k][2] * old[k][3])
            dx, dy = new[h][0] - old[h][0], new[h][1] - old[h][1]
            tx += dx; ty += dy
            x, y, w, hh = new[h]
            need_w = tx + tw + MIN_PAD - x; need_h = ty + th + MIN_PAD - y
            if tw <= 0 or th <= 0: continue
            if need_w > w: new[h][2] = need_w
            if need_h > hh: new[h][3] = need_h

    def apply_boxes(self, old, new):
        """写回形状新框，并把跟随元素（形状内文字、形状之间的小图标）按同样位移带走。"""
        for k, b in new.items(): self.B[k] = tuple(b)
        d = {k: (new[k][0] - old[k][0], new[k][1] - old[k][1]) for k in new}
        for n in self.nodes:
            r = self.role.get(n['id'])
            if r == 'text':
                h = self.parent.get(n['id'])
                if h in d:
                    x, y, w, hh = self.B[n['id']]; self.B[n['id']] = (x + d[h][0], y + d[h][1], w, hh)
            elif r == 'image':
                x, y, w, hh = self.B[n['id']]; c = (x + w / 2, y + hh / 2)
                host = min(d, key=lambda k: abs((old[k][0] + old[k][2] / 2) - c[0]) + abs((old[k][1] + old[k][3] / 2) - c[1]))
                self.B[n['id']] = (x + d[host][0], y + d[host][1], w, hh)

    def text_need(self, nid, shrink=MAX_SHRINK):
        """这个形状的文字在「分档字号最多缩 shrink」时需要多高（含最小内边距）。"""
        n = self.D[nid]; t = n.get('text') or {}
        s = (t.get('text') or '')
        if not s.strip(): return 0
        fs = self.fs_of(t.get('font_size') or 14) * (1 - shrink)
        bold = t.get('font_weight') == 'bold'
        w = self.B[nid][2] - MIN_PAD * 2
        if w <= 10: return 0
        rl = self.rich_model(n)
        if rl is not None:
            _, rows = self.wrap_rich(rl, w, 1e6, fs, True)
            nl = len(rows or [])
        else:
            nl = len(layout_text(s, w, 1e6, fs, bold, min_fs=fs)[0])
        return nl * fs * 1.4 + MIN_PAD * 2

    def widen_free_text(self):
        """不在任何形状里的独立文字（如大标题）单行放不下分档字号时，以中心为轴横向撑开，不缩字。"""
        n_w = 0
        shapes = [k for k in self.B if self.role.get(k) in SHAPE_ROLES]
        for n in self.nodes:
            if self.role.get(n['id']) != 'text' or self.parent.get(n['id']): continue
            t = n.get('text') or {}; s = (t.get('text') or '').strip()
            if not s or '\n' in s: continue
            fs = self.fs_of(t.get('font_size') or 14); bold = t.get('font_weight') == 'bold'
            x, y, w, h = self.B[n['id']]
            need = core_text.eff_width(s, fs, bold) + 4
            if need <= w: continue
            ha = t.get('horizontal_align', 'center')
            nx = x - (need - w) / 2 if ha == 'center' else (x - (need - w) if ha == 'right' else x)
            nb = (nx, y, need, h)
            if any(overlap_ratio(nb, self.B[k]) > 0 and not overlap_ratio((x, y, w, h), self.B[k]) > 0 for k in shapes): continue
            self.B[n['id']] = nb; n_w += 1
        return n_w

    def grow_rows(self, shrink):
        """文字放不下时撑高整行，位于该行下方的所有节点整体下移。标准档允许先缩字 10%，积极档不缩字。"""
        ids = [n['id'] for n in self.nodes if self.role.get(n['id']) in SHAPE_ROLES and not self.parent.get(n['id'])]
        if len(ids) < 2: return 0
        grown = 0
        for r in rows_of(self.B, ids):
            need = max([self.text_need(k, shrink) - self.B[k][3] for k in r] or [0])
            if need <= 1: continue
            bottom = max(self.B[k][1] + self.B[k][3] for k in r)
            for k in r:
                x, y, w, h = self.B[k]; self.B[k] = (x, y, w, h + need)
            for n in self.nodes:
                k = n['id']
                if k in r or k not in self.B: continue
                x, y, w, h = self.B[k]
                if y >= bottom - 1: self.B[k] = (x, y + need, w, h)
            grown += 1
        return grown

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
        bold = t.get('font_weight') == 'bold'
        ha, va = t.get('horizontal_align', 'center'), t.get('vertical_align', 'mid')
        if pad is None:
            pad = (8 if box[2] > 60 else 3) if self.mode == 'conservative' else (MIN_PAD if box[2] > 60 else 4)
        if self.mode != 'conservative':
            pad = min(pad, max(0.0, box[3] / 4))      # 很矮的条形容器不要被内边距吃掉
        fs = self.fs_of(t.get('font_size') or 14, box, s, bold, pad) * self.S
        nid = n.get('id')
        forced = nid in self.force
        if forced: fs = self.force[nid]
        color = self.text_color(n, host_paint)
        if self.rich(n, box, fs, color, ha, va, pad): return
        lo = max(9, fs * (0.7 if self.mode == 'conservative' else 1 - MAX_SHRINK - 0.05))
        lines, fs2 = layout_text(s, box[2] - pad * 2, box[3] - pad * 2, fs, bold, min_fs=fs if forced else lo)
        if self.mode != 'conservative' and len(lines) > 1 and '\n' not in s.strip() and len(s.strip()) <= 12:
            lo = fs if forced else lo
            # 短标签（≤ 12 字）不要拦腰折断：先在缩字下限内试单行
            for pd in (pad, min(pad, 4)):           # 不够时把左右内边距收窄到 4px 再试
                f = fs
                while f > lo and core_text.eff_width(s.strip(), f, bold) > box[2] - pd * 2: f -= 0.5
                if core_text.eff_width(s.strip(), f, bold) <= box[2] - pd * 2:
                    lines, fs2, pad = [s.strip()], f, pd; break
        if nid: self.fit[nid] = (fs, fs2)
        self.svg.text_block(box, lines, fs2, color, bold, ha, va, pad)

    def rich_model(self, n):
        """标准档的富文本：有列表符号或段内字重不一时返回行模型，否则 None（走普通排版）。"""
        rl = rich_lines(n)
        if not rl: return None
        ws = {b for _, sg in rl for _, b in sg}
        if any(mk for mk, _ in rl) or len(ws) > 1: return rl
        return None

    def rich(self, n, box, fs, color, ha, va, pad):
        """富文本：保留段内粗体与列表符号（• / 1.），按词元换行，续行悬挂缩进，放不下时整体缩字号。
        保守档沿用旧规则（只有每段都能单行放下时才走这条路径），以保证输出与 0.2.x 一致。"""
        if self.mode == 'conservative': return self.rich_legacy(n, box, fs, color, ha, va, pad)
        rl = self.rich_model(n)
        if rl is None: return False
        avail = box[2] - pad * 2
        f0 = fs
        fs, rows = self.wrap_rich(rl, avail, box[3] - pad * 2, fs, n.get('id') in self.force)
        if rows is None: return False
        if n.get('id'): self.fit[n['id']] = (f0, fs)
        accent = self.st['families']['blue']['soft']['text'] if color in (self.st['ink'], self.st['muted']) else color
        step = fs * 1.4
        y0 = box[1] + (box[3] - step * len(rows)) / 2 if va != 'top' else box[1] + pad
        for i, (mk, ind, segs, w) in enumerate(rows):
            # 对齐按检查器口径的宽度算（比实测宽），右/居中时才不会被判成右侧溢出
            tot = ind + max(w, sum(core_text.eff_width(t, fs, b) for t, b in segs))
            x = {'left': box[0] + pad, 'right': box[0] + box[2] - pad - tot}.get(ha, box[0] + (box[2] - tot) / 2)
            y = y0 + i * step + step / 2 + fs * 0.36
            if mk: self.svg.text(x, y, mk, fs, color, False)
            x += ind
            for s, b in segs:
                self.svg.text(x, y, s, fs, accent if b else color, b)
                x += text_width(s, fs, b)
        return True

    def rich_legacy(self, n, box, fs, color, ha, va, pad):
        paras = ((n.get('text') or {}).get('rich_text') or {}).get('paragraphs')
        if not paras or not any(e.get('text_element', {}).get('text_style', {}).get('font_weight') == 'bold'
                                for p in paras for e in p.get('elements', [])):
            return False
        P = [[(e['text_element']['text'], e['text_element'].get('text_style', {}).get('font_weight') == 'bold')
              for e in p.get('elements', []) if 'text_element' in e] for p in paras]
        avail = box[2] - pad * 2
        rows = []
        for segs in P:
            w = sum(text_width(t, fs, b) for t, b in segs)
            if w > avail: return False
            rows.append((segs, w))
        accent = self.st['families']['blue']['soft']['text'] if color in (self.st['ink'], self.st['muted']) else color
        step = fs * 1.6; y0 = box[1] + (box[3] - step * len(rows)) / 2 if va != 'top' else box[1] + pad
        for i, (segs, w) in enumerate(rows):
            x = {'left': box[0] + pad, 'right': box[0] + box[2] - pad - w}.get(ha, box[0] + (box[2] - w) / 2)
            for s, b in segs:
                self.svg.text(x, y0 + i * step + step / 2 + fs * 0.36, s, fs, accent if b else color, b)
                x += text_width(s, fs, b)
        return True

    def wrap_rich(self, lines, avail, avail_h, fs, fixed=False):
        """lines = [(列表符号, [(文字, 粗体), ...]), ...]。按词元折行（段内粗体保留、末行不留孤字、续行悬挂缩进），
        必要时缩字号。返回 (字号, [(符号, 缩进, 该行各段, 行宽)])；符号只出现在每项第一行。"""
        if avail <= 10: return fs, None
        lo = fs if fixed else max(9, fs * (1 - MAX_SHRINK - 0.05))
        while True:
            out = []
            ind_all = max([text_width(mk, fs) + fs * 0.45 for mk, _ in lines if mk] or [0])
            for mk, segs in lines:
                ind = ind_all if mk else 0
                if not segs: out.append(('', 0, [], 0.0)); continue
                for j, (sg, w) in enumerate(self.balance_para(segs, avail - ind, fs)):
                    out.append((mk if j == 0 else '', ind, sg, w))
            too_wide = any(o[1] + core_text.eff_width(''.join(x for x, _ in o[2]), fs, any(b for _, b in o[2])) > avail + 1
                           for o in out if o[2])
            # 短标签（每项 ≤ 12 字）被折成多行时，先尝试在缩字下限内放成一行
            short_broken = any(sum(len(t) for t, _ in sg) <= 12 and
                               sum(1 for o in out if o[2] and o[0] == mk) > 0 and
                               len(self.balance_para(sg, avail - (ind_all if mk else 0), fs)) > 1
                               for mk, sg in lines if sg)
            fits = len(out) * fs * 1.4 <= avail_h + fs * 0.4 and not too_wide
            if (fits and not short_broken) or fs <= lo:
                return fs, out
            fs -= 0.5

    def balance_para(self, segs, avail, fs):
        """一个段落折行：先按 avail 贪心，再在 0.62–1.0 倍宽度内找「行数不增、各行最均衡」的方案。"""
        base = self.greedy_para(segs, avail, fs)
        if len(base) < 2: return base
        def score(m):
            ws = [x[1] for x in m]
            ends = sum(1 for segs_, _ in m[:-1] if segs_ and segs_[-1][0][-1:] in '，、；：,;:')
            return (max(ws) - min(ws)) - ends * fs * 4          # 在标点后断行的方案优先
        best, bd, w = base, score(base), avail
        while w >= avail * 0.62:
            m = self.greedy_para(segs, w, fs)
            if len(m) > len(base): break
            sc = score(m)
            if sc < bd: best, bd = m, sc
            w -= 2
        return best

    def greedy_para(self, segs, avail, fs):
        out, cur, cw = [], [], 0.0
        for t, b in segs:
            for tk in core_text.tokens(t):
                w = core_text.eff_width(tk, fs, b)
                # 行首禁则：句读标点挂在上一行末尾（允许略超出 1 个字宽）
                if cur and cw + w > avail and not (tk in core_text.NO_LINE_START and cw + w <= avail + fs * 1.1):
                    out.append((cur, sum(text_width(x, fs, bb) for x, bb in cur))); cur, cw = [], 0.0
                    if not tk.strip(): continue
                if cur and cur[-1][1] == b: cur[-1] = (cur[-1][0] + tk, b)
                else: cur.append((tk, b))
                cw += w
        if cur: out.append((cur, sum(text_width(x, fs, bb) for x, bb in cur)))
        return out

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
            self.draw_text({'text': t}, (b[0], b[1] + 4, b[2], min(b[3], 44 * self.S + 16)), p,
                           pad=10 if self.mode == 'conservative' else 4)

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
        """检查器把「文字左上角所在的形状」当作文字容器，小图标（流程箭头等）压住文字就会被判成溢出。
        保守档沿用「压缩图标」的旧做法；标准档允许移动，直接把图标整体挪到文字块之外（挪动量最小的一侧）。"""
        M = 4
        if self.mode != 'conservative':
            for tx, ty, tw_, th in self.svg.texts:
                x0, y0 = min(p[0] for p in P), min(p[1] for p in P); x1, y1 = max(p[0] for p in P), max(p[1] for p in P)
                L, T, R, Bo = tx - M, ty - M, tx + tw_ + M, ty + th + M
                if x1 <= L or x0 >= R or y1 <= T or y0 >= Bo: continue
                opts = [(L - x1, 0), (R - x0, 0), (0, T - y1), (0, Bo - y0)]
                dx, dy = min(opts, key=lambda d: abs(d[0]) + abs(d[1]))
                P = [(px + dx, py + dy) for px, py in P]
                self.warn.append(f'image {nid} 与文字重叠，已移动 ({round(dx)}, {round(dy)})px')
            return P
        for tx, ty, tw_, th in self.svg.texts:
            x0, y0 = min(p[0] for p in P), min(p[1] for p in P); x1, y1 = max(p[0] for p in P), max(p[1] for p in P)
            if not (x0 < tx + M and tx - M < x1 and y0 < ty + M and ty - M < y1 and tx + tw_ > x1): continue
            if tx - x0 >= (x1 - x0) * 0.4:
                k = max(0.3, (tx - M - x0) / (x1 - x0)); P = [(x0 + (px - x0) * k, py) for px, py in P]
            else:
                k = max(0.3, (ty - M - y0) / (y1 - y0)); P = [(px, y0 + (py - y0) * k) for px, py in P]
            self.warn.append(f'image {nid} 盖住文字左上角，已压缩 {round((1 - k) * 100)}%')
        return P

    # 主流程
    def run(self):
        if self.mode == 'conservative': return self.draw_all()
        self.draw_all()
        self.force = self.unify_fit()
        self.svg = Svg(*self.svg_args); self.svg.FONT = self.font
        self.bgs, self.warn = {}, [w for w in self.warn if not w.startswith('image ')]
        return self.draw_all()

    def unify_fit(self):
        """同一父容器、同一行、同一原字号档的节点取放得下的最小字号（向下取整），让并列卡片字号一致。"""
        groups = {}
        for nid, (want, got) in self.fit.items():
            if self.role.get(nid) not in SHAPE_ROLES and self.role.get(nid) != 'text': continue
            groups.setdefault((self.parent.get(nid), round(want, 1)), []).append(nid)
        force, shrunk = {}, 0
        for (p, want), ids in groups.items():
            rows = rows_of(self.B, ids)
            for r in rows:
                m = min(self.fit[k][1] for k in r)
                v = float(int(m)) if m < want else want          # 缩过的取整数，避免 12.5 / 11.5 这类碎字号
                for k in r: force[k] = v
                if v < want: shrunk += len(r)
        self.layout_info['shrunk_text'] = shrunk
        return force

    def draw_all(self):
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
        return {'scale': self.S, 'mode': self.mode, 'font': self.font, **self.layout_info,
                'roles': dict(Counter(self.role.values())),
                'color_map': self.M.table(),
                'warnings': self.warn}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('raw'); ap.add_argument('-o', '--out', default='diagram.svg')
    ap.add_argument('--style', help='样式覆盖 JSON（extract_style.py 产出或手写）')
    ap.add_argument('--report', help='写出角色与配色映射报告 JSON')
    ap.add_argument('--map', action='append', default=[], help='强制原色归类，如 "#e8f8f3=teal/soft"')
    ap.add_argument('--scale', type=float)
    ap.add_argument('--mode', choices=['conservative', 'standard', 'aggressive'], default='standard',
                    help='conservative=只改配色（0.2.x 行为）；standard=加对齐/等距/统一尺寸/字号分档（默认）；aggressive=再按需撑高行')
    ap.add_argument('--font', help='统一字体，默认微软雅黑')
    ap.add_argument('--tiers', type=int, default=4, help='字号档数上限（默认 4）')
    a = ap.parse_args()
    ov = parse_maps(a.map)
    nodes = [n for n in load_raw(a.raw) if n['type'] != 'group']
    P = Painter(nodes, load_style(a.style), ov, a.scale, a.mode, a.font, a.tiers)
    P.run().save(a.out)
    rep = P.report()
    if a.report: json.dump(rep, open(a.report, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({'out': a.out, 'mode': rep['mode'], 'font': rep['font'], 'scale': rep['scale'],
                      'font_tiers': {k: v['count'] for k, v in (rep.get('font_tiers') or {}).items()},
                      'moved': sum(g.get('moved', 0) for g in (rep.get('layout') or [])),
                      'max_shift': max([g.get('max_shift', 0) for g in (rep.get('layout') or [])] or [0]),
                      'roles': rep['roles'], 'colors': len(rep['color_map']),
                      'warnings': len(rep['warnings'])}, ensure_ascii=False))
    for w in rep['warnings'][:10]: print('  !', w)


if __name__ == '__main__':
    main()
