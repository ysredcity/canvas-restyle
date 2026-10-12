"""PPT 适配器共用库：直接读写 .pptx 压缩包里的幻灯片 XML。

只改幻灯片（ppt/slides/slideN.xml）里 <a:srgbClr> 的颜色值与透明度，其余部件（母版、版式、主题、图片、图表、
动画、备注）逐字节原样复制。颜色决策来自 core（与飞书画板适配器同一套规则）。
"""
import os
import re
import sys
import zipfile
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from lxml import etree  # noqa: E402  python-pptx 的依赖

from core.color import family_of, hls, mix  # noqa: E402

A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
NS = {'a': A, 'p': P}
SLIDE_RE = re.compile(r'ppt/slides/slide(\d+)\.xml$')
TEXT_TAGS = {f'{{{A}}}rPr', f'{{{A}}}defRPr', f'{{{A}}}endParaRPr'}
SHAPE_TAGS = {f'{{{P}}}sp', f'{{{P}}}cxnSp', f'{{{P}}}grpSp', f'{{{P}}}pic', f'{{{P}}}graphicFrame'}


def slide_parts(z):
    """[(序号, 部件名)]，按页序。"""
    out = [(int(m.group(1)), n) for n in z.namelist() for m in [SLIDE_RE.match(n)] if m]
    return sorted(out)


def parse(z, name):
    return etree.fromstring(z.read(name))


def alpha_of(el):
    a = el.find('a:alpha', NS)
    return int(a.get('val')) / 1000 if a is not None else 100.0


def effective(hexv, alpha):
    """带透明度的颜色在白底上的观感色（幻灯片底色几乎都是白，用于判断深浅）。"""
    return mix(hexv, '#ffffff', 1 - alpha / 100) if alpha < 100 else hexv


def owner_shape(el):
    p = el.getparent()
    while p is not None and p.tag not in SHAPE_TAGS: p = p.getparent()
    return p


def context(el):
    """srgbClr 所在位置：fill / line / text / table / effect / other。"""
    chain = []
    p = el.getparent()
    while p is not None and p.tag not in SHAPE_TAGS:
        chain.append(etree.QName(p).localname); p = p.getparent()
    if 'effectLst' in chain or 'effectDag' in chain: return 'effect'
    if any(t in chain for t in ('rPr', 'defRPr', 'endParaRPr')): return 'text'
    if any(c in ('ln', 'lnRef') or re.fullmatch(r'ln[LRTB]|lnTlToBr|lnBlToTr', c) for c in chain): return 'line'
    if 'tcPr' in chain: return 'table'
    if any(c in chain for c in ('spPr', 'grpSpPr', 'fillRef', 'bg', 'bgPr')): return 'fill'
    return 'other'


def shape_fill(sp):
    """形状自身的纯色填充 srgbClr 元素（用于判断文字所在底色），没有则 None。"""
    if sp is None: return None
    sppr = sp.find('p:spPr', NS)
    if sppr is None: return None
    sf = sppr.find('a:solidFill/a:srgbClr', NS)
    return sf


def variant(hexv):
    """PPT 中的深浅：很浅 → soft（浅底），很深 → solid，其余 → accent（饱和强调色）。"""
    light = hls(hexv)[1]
    if light > 0.85: return 'soft'
    if light < 0.22: return 'solid'
    return 'accent'


def key(hexv, alpha, ctx, host=''):
    a = '' if alpha >= 100 else f'@{alpha:g}'
    return f'{ctx}:{hexv.upper()}{a}' + (f'|on:{host}' if host else '')


def color_refs(root):
    """遍历一页里所有 srgbClr：yield (元素, 原色 #rrggbb 小写, 透明度%, 位置, 所在形状)。"""
    for el in root.iter(f'{{{A}}}srgbClr'):
        v = el.get('val')
        if not v or not re.fullmatch(r'[0-9A-Fa-f]{6}', v): continue
        yield el, '#' + v.lower(), alpha_of(el), context(el), owner_shape(el)


def host_key(sp):
    f = shape_fill(sp)
    if f is None: return ''
    return key('#' + f.get('val').lower(), alpha_of(f), 'fill')


def scheme_counts(z):
    c = Counter()
    for _, n in slide_parts(z):
        for el in parse(z, n).iter(f'{{{A}}}schemeClr'): c[el.get('val')] += 1
    return dict(c)


def master_colors(z):
    """母版与版式里出现的彩色 srgb（按次数），用于识别品牌色。"""
    c = Counter()
    for n in z.namelist():
        if re.match(r'ppt/(slideMasters|slideLayouts)/[^/]+\.xml$', n):
            for v in re.findall(rb'srgbClr val="([0-9A-Fa-f]{6})"', z.read(n)):
                h = '#' + v.decode().lower()
                if family_of(h)[0] not in (None, 'neutral'): c[h] += 1
    return c.most_common()


def master_themes(z):
    """幻灯片母版使用的主题部件名（备注 / 讲义母版的主题不算）。"""
    out = []
    for n in z.namelist():
        m = re.match(r'ppt/slideMasters/_rels/(slideMaster\d+)\.xml\.rels$', n)
        if m:
            for t in re.findall(rb'Target="\.\./theme/(theme\d+\.xml)"', z.read(n)):
                p = 'ppt/theme/' + t.decode()
                if p not in out: out.append(p)
    return out


THEME_SLOTS = ('accent1', 'accent2', 'accent3', 'accent4', 'accent5', 'accent6')


def theme_accents(root):
    """主题色方案里的 accent1–6：yield (槽位名, srgbClr 元素, 原色)。dk/lt/超链接色不动。"""
    cs = root.find('.//a:clrScheme', NS)
    if cs is None: return
    for slot in THEME_SLOTS:
        el = cs.find(f'a:{slot}/a:srgbClr', NS)
        if el is not None and re.fullmatch(r'[0-9A-Fa-f]{6}', el.get('val') or ''):
            yield slot, el, '#' + el.get('val').lower()


def open_pptx(path):
    if not path.lower().endswith('.pptx'):
        raise SystemExit('只支持 .pptx；.ppt / .key 请先在 PowerPoint 或 Keynote 里另存为 .pptx。')
    return zipfile.ZipFile(path)
