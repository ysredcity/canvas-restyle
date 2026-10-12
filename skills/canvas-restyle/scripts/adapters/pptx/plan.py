#!/usr/bin/env python3
"""PPT 适配器 · 第 1 步：扫描整份 .pptx，生成样式方案 plan.json（不改文件）。

方案按整份 PPT 生成：同一原色（同一位置类型）在所有页上都换成同一个新色。
规则（与飞书画板适配器共用 core 的色系归类与色板）：
- 彩色按色相归入 7 个色系；同色系、同深浅的近似色收敛为同一个新色；不同色系保持区分。
- 中性色（黑、白、灰）不改：PPT 正文默认继承母版的黑色，只改显式颜色会造成同段文字深浅不一。
- 母版里最常用的彩色视为品牌色：品牌色本身不改，同色系近似色收敛到它（可用 --brand 指定或 --brand none 关闭）。
- 主题色：母版主题的 accent1–6 按同样规则改定义（引用主题色的形状随之统一），dk/lt/超链接色不动；
  图片、图表、SmartArt 不涉及。

用法：python3 plan.py in.pptx -o plan.json [--brand "#00aaa6"|none] [--style style.json] [--map "#ffb940=amber/accent"]
"""
import argparse
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pptx_lib import (color_refs, effective, host_key, key, master_colors, master_themes, open_pptx,  # noqa: E402
                      parse, scheme_counts, slide_parts, theme_accents, variant)

from core.color import contrast, family_of  # noqa: E402
from core.palette import anchor_family, load_style, parse_maps  # noqa: E402


def classify(hexv, alpha, ov):
    eff = effective(hexv, alpha)
    if hexv in ov: return ov[hexv]
    fam, _ = family_of(eff)
    return fam, variant(eff)


def decide_fill(st, hexv, alpha, ov):
    fam, var = classify(hexv, alpha, ov)
    if fam in (None, 'neutral'): return None, '中性色不改'
    p = st['families'][fam][var if var in st['families'][fam] else 'accent']
    drop = alpha < 100 and var == 'soft'          # 浅色半透明底：换成等效的不透明浅底
    return {'to': p['bg'], 'drop_alpha': drop, 'family': fam, 'variant': var}, None


def decide_line(st, hexv, alpha, ov):
    fam, var = classify(hexv, alpha, ov)
    if fam in (None, 'neutral'): return None, '中性色不改'
    F = st['families'][fam]
    to = F['soft']['border'] if var == 'soft' else F[var if var in F else 'accent']['bg']
    return {'to': to, 'drop_alpha': False, 'family': fam, 'variant': var}, None


def decide_text(st, hexv, alpha, host, ov):
    fam, var = classify(hexv, alpha, ov)
    if fam in (None, 'neutral'): return None, '中性色不改'
    if host and host['variant'] in ('accent', 'solid'):     # 彩色底上的彩色字 → 该底色配套的文字色
        F = st['families'][host['family']]
        return {'to': F[host['variant']]['text'], 'drop_alpha': False, 'family': host['family'], 'variant': 'on-' + host['variant']}, None
    return {'to': st['families'][fam]['soft']['text'], 'drop_alpha': False, 'family': fam, 'variant': 'text'}, None


def build(path, brand=None, style=None, maps=None):
    z = open_pptx(path)
    st = load_style(style); ov = parse_maps(maps)
    mc = master_colors(z)
    b = None
    if brand != 'none':
        bc = (brand or (mc[0][0] if mc else '')).lower()
        if bc:
            fam = anchor_family(st, bc)
            if fam: b = {'color': bc, 'family': fam, 'source': '--brand' if brand else '母版最常用彩色'}
    mapping, kept, warn = {}, {}, []
    fills = {}
    # 主题强调色（accent1–6）：幻灯片里引用主题色的形状随之统一；品牌色同理不改
    # 只改幻灯片实际引用到的槽位；两个槽位不能收敛成同一色（图表系列靠它们区分），撞色时后者保持原样
    used = scheme_counts(z)
    for tp in master_themes(z):
        taken = {}
        for slot, el, hexv in theme_accents(parse(z, tp)):
            d, why = decide_fill(st, hexv, 100, ov)
            if d and not used.get(slot): d, why = None, '幻灯片未引用此主题色'
            if d and d['to'] in taken:
                warn.append(f'主题 {slot} 与 {taken[d["to"]]} 会收敛成同一色 {d["to"]}，为保留区分，{slot} 保持原样')
                d, why = None, f'与 {taken[d["to"]]} 撞色，保持原样'
            if d: taken[d['to']] = slot
            k = f'theme:{tp}:{slot}:{hexv.upper()}'
            if d: mapping[k] = {**d, 'count': 1, 'slides': []}
            else: kept[k] = {'reason': why, 'count': 1, 'slides': []}
    for idx, name in slide_parts(z):
        root = parse(z, name)
        refs = list(color_refs(root))
        for el, hexv, alpha, ctx, sp in refs:             # 先定形状底色，文字要参照它
            if ctx in ('fill', 'table'):
                k = key(hexv, alpha, ctx)
                d, why = decide_fill(st, hexv, alpha, ov)
                rec = mapping if d else kept
                rec.setdefault(k, {**(d or {'reason': why}), 'count': 0, 'slides': []})
                rec[k]['count'] += 1
                if idx not in rec[k]['slides']: rec[k]['slides'].append(idx)
                fills[k] = d
        for el, hexv, alpha, ctx, sp in refs:
            if ctx in ('fill', 'table'): continue
            if ctx == 'line': k = key(hexv, alpha, ctx); d, why = decide_line(st, hexv, alpha, ov)
            elif ctx == 'text':
                hk = host_key(sp); k = key(hexv, alpha, ctx, hk)
                d, why = decide_text(st, hexv, alpha, fills.get(hk), ov)
            else:
                k = key(hexv, alpha, ctx); d, why = None, f'{ctx} 中的颜色不改'
            rec = mapping if d else kept
            rec.setdefault(k, {**(d or {'reason': why}), 'count': 0, 'slides': []})
            rec[k]['count'] += 1
            if idx not in rec[k]['slides']: rec[k]['slides'].append(idx)
        # 对比度复核：形状底色被改后，原样保留的中性文字是否仍然清楚
        for el, hexv, alpha, ctx, sp in refs:
            if ctx != 'text': continue
            hk = host_key(sp); hd = fills.get(hk)
            if not hd: continue
            tk = key(hexv, alpha, ctx, hk)
            tc = mapping[tk]['to'] if tk in mapping else hexv
            c = contrast(tc, hd['to'])
            if c < 3:
                warn.append(f'第 {idx} 页：文字 {tc} 在新底色 {hd["to"]} 上对比度 {c:.1f}（<3）')
    # 收敛统计：多个原色 → 同一新色
    merged = defaultdict(set)
    for k, v in mapping.items(): merged[(k.split(':')[0], v['to'])].add(k.split(':')[-1].split('|')[0] if k.startswith('theme:') else k.split(':', 1)[1].split('|')[0])
    conv = [{'context': c, 'to': t, 'from': sorted(fs)} for (c, t), fs in merged.items() if len(fs) > 1]
    return {
        'source': os.path.abspath(path), 'brand': b, 'style': style, 'overrides': {k: list(v) for k, v in ov.items()},
        'map': mapping, 'kept': kept, 'converged': conv, 'scheme_refs_unchanged': scheme_counts(z),
        'master_colors': mc[:8], 'warnings': sorted(set(warn)),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pptx'); ap.add_argument('-o', '--out', default='plan.json')
    ap.add_argument('--brand', help='品牌色 hex；none 表示不锚定品牌色。默认取母版最常用彩色')
    ap.add_argument('--style', help='样式覆盖 JSON'); ap.add_argument('--map', action='append', default=[])
    a = ap.parse_args()
    plan = build(a.pptx, a.brand, a.style, a.map)
    json.dump(plan, open(a.out, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({'out': a.out, 'brand': plan['brand'], 'changed_keys': len(plan['map']),
                      'changed_refs': sum(v['count'] for v in plan['map'].values()),
                      'kept_refs': sum(v['count'] for v in plan['kept'].values()),
                      'converged': len(plan['converged']), 'warnings': len(plan['warnings'])}, ensure_ascii=False))
    for w in plan['warnings'][:10]: print('  !', w)


if __name__ == '__main__':
    main()
