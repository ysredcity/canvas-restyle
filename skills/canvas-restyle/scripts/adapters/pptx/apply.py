#!/usr/bin/env python3
"""PPT 适配器 · 第 2 步：按 plan.json 原位改色，写出新文件（原文件只读）。

只改幻灯片 XML 里 <a:srgbClr> 的 val（以及方案要求时去掉 <a:alpha>）和母版主题的 accent1–6；其他部件逐字节复制，
所以母版、动画、备注、超链接、图片、图表和每个形状的位置尺寸都不变。

用法：python3 apply.py in.pptx plan.json -o "XX（优化版）.pptx"
"""
import argparse
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pptx_lib import NS, color_refs, host_key, key, master_themes, open_pptx, slide_parts, theme_accents  # noqa: E402
from lxml import etree  # noqa: E402


def apply(src, plan, out):
    if os.path.abspath(src) == os.path.abspath(out):
        raise SystemExit('输出不能覆盖原文件。')
    M = plan['map']
    zin = open_pptx(src)
    slides = dict((n, i) for i, n in slide_parts(zin))
    themes = set(master_themes(zin))
    changed, miss = 0, set()
    with zipfile.ZipFile(out, 'w') as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename in slides:
                root = etree.fromstring(data)
                todo = []
                for el, hexv, alpha, ctx, sp in color_refs(root):     # 先算全部键（文字要参照原底色），再改
                    k = key(hexv, alpha, ctx, host_key(sp) if ctx == 'text' else '')
                    todo.append((el, k))
                for el, k in todo:
                    d = M.get(k)
                    if not d:
                        if k not in plan['kept']: miss.add(k)
                        continue
                    el.set('val', d['to'].lstrip('#').upper())
                    if d.get('drop_alpha'):
                        a = el.find('a:alpha', NS)
                        if a is not None: el.remove(a)
                    changed += 1
                data = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
            elif info.filename in themes:
                root = etree.fromstring(data); hit = False
                for slot, el, hexv in list(theme_accents(root)):
                    d = M.get(f'theme:{info.filename}:{slot}:{hexv.upper()}')
                    if d: el.set('val', d['to'].lstrip('#').upper()); changed += 1; hit = True
                if hit: data = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
            zi = zipfile.ZipInfo(info.filename, info.date_time); zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = info.external_attr; zout.writestr(zi, data)
    if miss:
        print(f'  ! {len(miss)} 个颜色不在方案里（原样保留），方案可能不是用这份文件生成的：{sorted(miss)[:5]}')
    return changed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pptx'); ap.add_argument('plan'); ap.add_argument('-o', '--out', required=True)
    a = ap.parse_args()
    n = apply(a.pptx, json.load(open(a.plan)), a.out)
    print(json.dumps({'out': a.out, 'changed_refs': n}, ensure_ascii=False))


if __name__ == '__main__':
    main()
