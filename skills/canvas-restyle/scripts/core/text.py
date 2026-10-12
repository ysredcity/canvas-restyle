"""文字测量与换行。与具体工具无关。

装了 Pillow 且能找到 Noto Sans SC（默认在 whiteboard-cli 自带字体目录，或用环境变量 WB_FONT_DIR 指定）时，
文字宽度用字体实测，否则退回估算系数。
"""
import glob
import os
import re

_FONT_DIR = None
_fonts = {}


def _font_dir():
    global _FONT_DIR
    if _FONT_DIR is None:
        env = os.environ.get('WB_FONT_DIR')
        cands = ([env] if env else []) + sorted(glob.glob(os.path.expanduser(
            '~/.npm/_npx/*/node_modules/@larksuite/whiteboard-cli/dist/fonts')))
        _FONT_DIR = next((d for d in cands if os.path.exists(os.path.join(d, 'NotoSansSC-Regular.ttf'))), '')
    return _FONT_DIR


def _font(bold, size):
    key = (bold, round(size * 10))
    if key not in _fonts:
        try:
            from PIL import ImageFont
            fd = _font_dir()
            _fonts[key] = ImageFont.truetype(os.path.join(fd, 'NotoSansSC-Bold.ttf' if bold else 'NotoSansSC-Regular.ttf'),
                                             round(size * 10)) if fd else None
        except Exception:
            _fonts[key] = None
    return _fonts[key]


def text_width(t, fs, bold=False):
    f = _font(bold, fs)
    if f is not None:
        return f.getlength(t) / 10
    return sum(fs * (1 if ord(ch) > 255 else (0.3 if ch == ' ' else (0.62 if bold else 0.56))) for ch in t)


NO_LINE_START = '，。、；：！？）)】」』》,.;:!?%'


def wrap(t, w, fs, bold=False):
    """按词元换行：英文/数字串不拆开，行首标点挂回上一行。"""
    toks = re.findall(r'[A-Za-z0-9_.%+-]+|\s+|.', t)
    lines, cur = [], ''
    for tk in toks:
        if cur and text_width(cur + tk, fs, bold) > w:
            lines.append(cur.rstrip()); cur = tk.lstrip()
        else:
            cur += tk
    if cur.strip(): lines.append(cur.rstrip())
    for i in range(1, len(lines)):
        while lines[i] and lines[i][0] in NO_LINE_START:
            lines[i - 1] += lines[i][0]; lines[i] = lines[i][1:]
    return [l for l in lines if l]


def bwrap(t, w, fs, bold=False):
    """均衡换行：行数不变，各行宽度尽量相近（避免末行孤字）。"""
    base = wrap(t, w, fs, bold)
    if len(base) < 2: return base
    best, bd, ww = base, 1e9, w
    while ww >= w * 0.55:
        m = wrap(t, ww, fs, bold)
        if len(m) > len(base): break
        ws = [text_width(x, fs, bold) for x in m]
        if max(ws) - min(ws) < bd: best, bd = m, max(ws) - min(ws)
        ww -= 2
    return best


def layout_text(t, w, h, fs, bold=False, min_fs=10, lh=1.4):
    """在 w×h 内排版：保留原硬换行，超宽则均衡换行，放不下则逐步缩小字号。返回 (lines, fs)。"""
    paras = t.replace('\r', '').split('\n')
    while True:
        lines = []
        for p in paras:
            lines += bwrap(p, w, fs, bold) if p.strip() else ['']
        fits_h = len(lines) * fs * lh <= h + fs * 0.4
        fits_w = all(text_width(l, fs, bold) <= w + 1 for l in lines)   # 不可断的长词也要放得下
        if fs <= min_fs or (fits_h and fits_w):
            return lines, fs
        fs -= 0.5
