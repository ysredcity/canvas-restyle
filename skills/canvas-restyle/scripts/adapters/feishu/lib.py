"""飞书画板适配器共用库：raw 读取、坐标、SVG 构建。颜色与文字测量来自 core。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.color import family_of, hex2rgb, hls, luminance  # noqa: F401  （供本适配器各脚本沿用旧导入）
from core.text import NO_LINE_START, bwrap, layout_text, text_width, wrap  # noqa: F401

# ---------------------------------------------------------------- raw 读取
OFFSET_PARENTS = ('section', 'table')        # 子节点坐标相对这些父节点；group 子节点为绝对坐标


def load_raw(path):
    data = json.load(open(path))
    return data['nodes'] if isinstance(data, dict) else data


def index(nodes):
    return {n['id']: n for n in nodes}


def abs_box(n, D):
    """节点绝对坐标 (x, y, w, h)：逐级累加 section / table 父节点偏移。"""
    x, y = n.get('x', 0), n.get('y', 0)
    p = n.get('parent_id')
    while p and p in D and D[p]['type'] in OFFSET_PARENTS:
        x += D[p]['x']; y += D[p]['y']; p = D[p].get('parent_id')
    return x, y, n.get('width', 0), n.get('height', 0)


def node_text(n):
    """节点上的全部可见文字（形状文字 / 表格单元格 / section 标题）。"""
    out = []
    t = (n.get('text') or {}).get('text')
    if t: out.append(t)
    if n['type'] == 'section':
        s = (n.get('section') or {}).get('title')
        if s: out.append(s)
    if n['type'] == 'table':
        for c in n['table'].get('cells', []):
            ct = (c.get('text') or {}).get('text')
            if ct: out.append(ct)
    return out


# ---------------------------------------------------------------- 富文本
def rich_lines(n):
    """把节点的富文本拆成「行」：[(列表符号, [(文字, 是否粗体), ...]), ...]。
    - paragraph_type 1 = 无序列表（•），2 = 有序列表（1. 2. …，连续的有序段落连续编号）；
    - 一个段落里夹着的硬换行（\n / \r\n）拆成多行，列表编号顺延；
    - 片段没写字重时继承节点字重。
    没有富文本时返回 None。列表符号是原画板的显示效果，不在 text 字段里，verify_text 会按同一规则计入。"""
    t = n.get('text') or {}
    paras = (t.get('rich_text') or {}).get('paragraphs')
    if not paras: return None
    base = t.get('font_weight') == 'bold'
    out, num = [], 0
    for p in paras:
        kind = p.get('paragraph_type', 0)
        if kind == 2: num = num + 1 if num else (p.get('list_begin_index') or 0) + 1
        else: num = 0
        segs, cur = [], []
        for e in p.get('elements', []):
            te = e.get('text_element')
            if not te: continue
            w = (te.get('text_style') or {}).get('font_weight')
            b = base if w is None else (w == 'bold')
            parts = te.get('text', '').replace('\r\n', '\n').replace('\r', '\n').split('\n')
            for i, part in enumerate(parts):
                if i > 0: segs.append(cur); cur = []
                if part: cur.append((part, b))
        segs.append(cur)
        for i, sg in enumerate(segs):
            if i > 0 and not sg: continue           # 段末换行留下的空行
            if kind == 2 and i > 0: num += 1
            mk = '•' if kind == 1 else (f'{num}.' if kind == 2 else '')
            out.append((mk if sg else '', sg))
    return out


def list_marker_chars(n):
    """该节点渲染时会多出来的列表符号字符（供 verify_text 计入原画板一侧）。"""
    return ''.join(mk for mk, _ in (rich_lines(n) or []) if mk)


# ---------------------------------------------------------------- SVG
def esc(t):
    return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


class Svg:
    FONT = 'Noto Sans SC'

    def __init__(self, w, h, bg=None):
        self.w, self.h, self.o = w, h, []
        self.texts = []          # 已绘文字的近似外框 (left, top, w, h)，供图标避让
        self.o.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" viewBox="0 0 {w:.0f} {h:.0f}">')
        self.o.append(f'<defs><filter id="sh" filterUnits="userSpaceOnUse" x="-40" y="-40" width="{w + 80:.0f}" height="{h + 80:.0f}">'
                      f'<feDropShadow dx="0" dy="2" stdDeviation="4" flood-color="#0f2a3d" flood-opacity="0.07"/></filter></defs>')
        if bg: self.rect(0, 0, w, h, bg)

    def add(self, s): self.o.append(s)

    def rect(self, x, y, w, h, fill='none', stroke=None, rx=0, sw=1, dash=None, shadow=False):
        s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ''
        d = f' stroke-dasharray="{dash}"' if dash else ''
        f = ' filter="url(#sh)"' if shadow else ''
        self.o.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w, 0):.1f}" height="{max(h, 0):.1f}" rx="{rx}" fill="{fill}"{s}{d}{f}/>')

    def rpoly(self, x, y, w, h, fill='none', stroke=None, r=10, sw=1, dash=None, shadow=False, seg=4):
        """圆角矩形的多边形近似。whiteboard-cli 的重叠检查不计 polygon，大容器 / 条纹 / 表格底用它画，
        可避免「被包含形状 ≥50%」与「部分重叠 ≥50%」的误报。"""
        import math
        r = max(0, min(r, w / 2, h / 2)); pts = []
        for cx, cy, a0 in ((x + w - r, y + r, -90), (x + w - r, y + h - r, 0), (x + r, y + h - r, 90), (x + r, y + r, 180)):
            for k in range(seg + 1):
                a = math.radians(a0 + 90 * k / seg); pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ''
        d = f' stroke-dasharray="{dash}"' if dash else ''
        f = ' filter="url(#sh)"' if shadow else ''
        p = ' '.join(f'{px:.1f},{py:.1f}' for px, py in pts)
        self.o.append(f'<polygon points="{p}" fill="{fill}"{s}{d}{f}/>')

    def line(self, x1, y1, x2, y2, c, sw=1, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ''
        self.o.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{c}" stroke-width="{sw}"{d}/>')

    def polyline(self, pts, c, sw=1, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ''
        p = ' '.join(f'{x:.1f},{y:.1f}' for x, y in pts)
        self.o.append(f'<polyline points="{p}" fill="none" stroke="{c}" stroke-width="{sw}"{d}/>')

    def polygon(self, pts, fill, stroke=None, sw=1):
        s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ''
        p = ' '.join(f'{x:.1f},{y:.1f}' for x, y in pts)
        self.o.append(f'<polygon points="{p}" fill="{fill}"{s}/>')

    def text(self, x, y, t, fs, fill, bold=False, anchor='start'):
        w = 'bold' if bold else 'normal'
        tw_ = text_width(t, fs, bold)
        left = {'middle': x - tw_ / 2, 'end': x - tw_}.get(anchor, x)
        self.texts.append((left, y - fs * 1.05, tw_, fs * 1.3))
        self.o.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{fs:g}" font-family="{self.FONT}" font-weight="{w}" '
                      f'fill="{fill}" text-anchor="{anchor}">{esc(t)}</text>')

    def text_block(self, box, lines, fs, fill, bold=False, halign='center', valign='mid', pad=8, lh=1.4):
        x, y, w, h = box
        step = fs * lh; total = len(lines) * step
        if valign == 'top': y0 = y + pad
        elif valign == 'bottom': y0 = y + h - pad - total
        else: y0 = y + (h - total) / 2
        ax = {'left': x + pad, 'right': x + w - pad}.get(halign, x + w / 2)
        an = {'left': 'start', 'right': 'end'}.get(halign, 'middle')
        for i, l in enumerate(lines):
            if l: self.text(ax, y0 + i * step + step / 2 + fs * 0.36, l, fs, fill, bold, an)

    def save(self, path):
        open(path, 'w').write('\n'.join(self.o + ['</svg>']))
