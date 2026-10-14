"""颜色工具：解析、色系归类、亮度。与具体工具无关。"""
import colorsys
import re


def hex2rgb(h):
    h = (h or '').strip().lstrip('#')
    if len(h) == 3: h = ''.join(c * 2 for c in h)
    if len(h) != 6 or not re.fullmatch(r'[0-9a-fA-F]{6}', h): return None
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def hls(h):
    rgb = hex2rgb(h)
    return colorsys.rgb_to_hls(*rgb) if rgb else None   # (hue, light, sat)


def family_of(h):
    """原色 → (色系, 深浅)。色系：neutral/red/amber/green/teal/blue/purple；深浅：solid/soft/white。"""
    v = hls(h)
    if v is None: return None, None
    hue, light, sat = v[0] * 360, v[1], v[2]
    if light > 0.97 and sat < 0.5: return 'neutral', 'white'
    if sat < 0.12 or (light > 0.93 and sat < 0.25): return 'neutral', ('solid' if light < 0.6 else 'soft')
    # 近黑色：很深时即使带一点色相，看上去也是黑的（如飞书默认文字色 #1f2329，饱和度 0.14）。
    # 深彩色（如深青 #0f5c6e，饱和度 0.76）饱和度高，不受影响。
    if light < 0.25 and sat < 0.35: return 'neutral', 'solid'
    if hue < 15 or hue >= 345: fam = 'red'
    elif hue < 65: fam = 'amber'
    elif hue < 160: fam = 'green'
    elif hue < 195: fam = 'teal'
    elif hue < 255: fam = 'blue'
    else: fam = 'purple'
    return fam, ('solid' if light < 0.62 else 'soft')


def luminance(h):
    rgb = hex2rgb(h)
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2] if rgb else 1




def rgb2hex(rgb):
    return '#' + ''.join(f'{max(0, min(255, round(c * 255))):02x}' for c in rgb)


def mix(a, b, t):
    """a 与 b 按 t 混合（t=0 → a，t=1 → b）。"""
    ra, rb = hex2rgb(a), hex2rgb(b)
    return rgb2hex(tuple(x + (y - x) * t for x, y in zip(ra, rb)))


def rel_lum(h):
    """WCAG 相对亮度。"""
    def ch(c): return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = hex2rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b):
    la, lb = sorted((rel_lum(a), rel_lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)
