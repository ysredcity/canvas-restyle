#!/usr/bin/env python3
"""参考模式·样式迁移：从参考画板 raw 提取配色，生成 redraw.py 可用的 --style 覆盖文件。

用法：python3 extract_style.py reference/raw.json -o style.json
只迁移颜色（各色系的 soft/solid 底色、描边、文字色，以及页面底、墨色、连线色）；
不迁移版式。参考画板若本身是我们生成的（多为多边形/矩形转成的形状），同样适用。
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import family_of, load_raw, luminance


def lower(c): return (c or '').lower() or None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('raw'); ap.add_argument('-o', '--out', default='style.json')
    a = ap.parse_args()
    ns = load_raw(a.raw)
    fills = collections.defaultdict(collections.Counter)      # (fam, var) -> 底色计数
    borders = collections.defaultdict(collections.Counter)    # (fam, var) -> 描边计数
    texts = collections.defaultdict(collections.Counter)      # (fam, var) -> 文字色计数
    inks, lines = collections.Counter(), collections.Counter()
    for n in ns:
        st = n.get('style') or {}; f = lower(st.get('fill_color')); b = lower(st.get('border_color'))
        tc = lower((n.get('text') or {}).get('text_color'))
        if n['type'] == 'connector' and b: lines[b] += 1; continue
        if f:
            k = family_of(f)
            if k[0]:
                w = max(1, n.get('width', 0) * n.get('height', 0) ** 0.5 / 100)
                fills[k][f] += w
                if b: borders[k][b] += 1
                if tc: texts[k][tc] += 1
        elif tc and luminance(tc) < 0.3 and family_of(tc)[0] == 'neutral':
            inks[tc] += 1
    fam = {}
    for (f, v), c in fills.items():
        if f == 'neutral' and v == 'white': continue
        entry = {'bg': c.most_common(1)[0][0]}
        if borders[(f, v)]: entry['border'] = borders[(f, v)].most_common(1)[0][0]
        if texts[(f, v)]:
            t = texts[(f, v)].most_common(1)[0][0]
            # 文字与底色对比不足时不迁移文字色，保留默认
            if abs(luminance(t) - luminance(entry['bg'])) > 0.35: entry['text'] = t
        fam.setdefault(f, {})[v] = entry
    out = {'name': 'from-reference', 'families': fam}
    if inks: out['ink'] = inks.most_common(1)[0][0]
    if lines: out['connector'] = lines.most_common(1)[0][0]
    json.dump(out, open(a.out, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({'out': a.out, 'families': {k: sorted(v) for k, v in fam.items()},
                      'ink': out.get('ink'), 'connector': out.get('connector')}, ensure_ascii=False))
    if not fam: print('  ! 参考画板没有可识别的彩色形状，样式迁移无效；考虑数据驱动或默认色板。')


if __name__ == '__main__':
    main()
