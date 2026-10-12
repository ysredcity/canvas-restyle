"""样式决策（与具体工具无关）：读色板、原色 → 新色映射、文字颜色规则。

所有适配器都通过这里决定「每个元素该变成什么颜色」，保证飞书画板、PPT 等走同一套视觉原则：
- 原色按色相归入 7 个色系（core.color.family_of），同一原色始终映射为同一新色；
- 色系内只用 soft（浅底）/ solid（深底白字）/ white（白卡）三种深浅；
- 文字颜色只用墨色、弱化灰、所在色系文字色、白色四种。
"""
import json
import os

from core.color import contrast, family_of, luminance, mix

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PALETTE = os.path.join(HERE, 'palette.json')


def load_style(path=None):
    """默认色板 + 可选覆盖（两级字典合并）。"""
    st = json.load(open(DEFAULT_PALETTE))
    if path:
        ov = json.load(open(path))
        for k, v in ov.items():
            if isinstance(v, dict) and isinstance(st.get(k), dict):
                for k2, v2 in v.items():
                    if isinstance(v2, dict) and isinstance(st[k].get(k2), dict): st[k][k2].update(v2)
                    else: st[k][k2] = v2
            else:
                st[k] = v
    return st


def parse_maps(items):
    """命令行 --map "#e8f8f3=teal/soft" → {原色: (色系, 深浅)}。"""
    ov = {}
    for m in items or []:
        k, v = m.split('='); fam, var = v.split('/'); ov[k.strip().lower()] = (fam, var)
    return ov


class Mapper:
    """原色 → 新色。同一原色始终映射到同一结果，并记录映射表供报告。"""

    def __init__(self, st, overrides):
        self.st, self.ov, self.log = st, overrides, {}

    def fam(self, color):
        if color in self.ov: return self.ov[color]
        fam, var = family_of(color)
        if fam == 'neutral' and var == 'white': return fam, 'white'
        return fam, var

    def paint(self, color, role):
        """返回 (色系, 深浅, {bg, border, text})；无法解析的颜色返回 None。"""
        if not color:
            return None
        fam, var = self.fam(color)
        if fam is None: return None
        fams = self.st['families']
        var = var if var in fams[fam] else 'soft'
        p = fams[fam][var]
        self.log.setdefault(color, {'family': fam, 'variant': var, 'bg': p['bg'], 'roles': set()})['roles'].add(role)
        return fam, var, p

    def table(self):
        return {k: {**v, 'roles': sorted(v['roles'])} for k, v in self.log.items()}


def anchor_family(st, color):
    """品牌色锚定：把 color 所在色系的 accent 设为 color 本身，soft / solid 由它推导。
    用于 PPT 母版等已有品牌色的场景——品牌色本身不改，同色系的近似色统一收敛到它。返回色系名。"""
    color = color.lower()
    fam, _ = family_of(color)
    if fam in (None, 'neutral'): return None
    on = '#ffffff' if contrast(color, '#ffffff') >= 3 else st['ink']
    st['families'][fam] = {
        'accent': {'bg': color, 'border': mix(color, '#000000', 0.18), 'text': on},
        'soft': {'bg': mix(color, '#ffffff', 0.9), 'border': mix(color, '#ffffff', 0.5), 'text': mix(color, '#000000', 0.45)},
        'solid': {'bg': mix(color, '#000000', 0.25), 'border': mix(color, '#000000', 0.4), 'text': '#ffffff'},
    }
    return fam


def text_color(st, tc, host_paint):
    """文字颜色：深底 → 白 / 原色深 → 墨色 / 灰 → 弱化 / 彩色 → 所在色系文字色。
    tc 为原文字色（小写 hex，可为 None），host_paint 为所在形状的 Mapper.paint 结果。"""
    tc = (tc or '#1f2329').lower()
    if host_paint and host_paint[1] == 'solid': return host_paint[2]['text']
    lum = luminance(tc)
    fam, var = family_of(tc)
    if lum > 0.85: return host_paint[2]['text'] if host_paint and host_paint[1] == 'solid' else st['ink']
    if fam == 'neutral' or fam is None: return st['muted'] if lum > 0.32 else st['ink']
    return st['families'][fam]['soft']['text']
