#!/usr/bin/env python3
"""PPT 适配器 · 第 3 步：证明「只改了颜色」。

1. 部件清单一致，幻灯片与主题以外的部件（母版、版式、图片、图表、备注……）逐字节相同；主题只允许颜色值不同；
2. 每页 XML 把 srgbClr 的颜色值和透明度抹掉后完全相同 —— 形状数量、层级、位置、尺寸、文字、字号、动画都没变；
3. 用 python-pptx 能正常打开，逐页文字一致。
全部通过输出 `ok`，否则退出码 1。

用法：python3 verify.py 原文件.pptx 优化版.pptx
"""
import argparse
import sys
import zipfile

from lxml import etree

A = 'http://schemas.openxmlformats.org/drawingml/2006/main'


def canon(data):
    root = etree.fromstring(data)
    for el in root.iter(f'{{{A}}}srgbClr'):
        el.set('val', 'X')
        for a in el.findall(f'{{{A}}}alpha'): el.remove(a)
    return etree.tostring(root, method='c14n')


def slide_texts(path):
    from pptx import Presentation
    out = []
    def walk(shapes):
        for s in shapes:
            if s.has_text_frame: yield s.text_frame.text
            if s.shape_type == 6: yield from walk(s.shapes)
            if getattr(s, 'has_table', False) and s.has_table:
                for r in s.table.rows:
                    for c in r.cells: yield c.text
    for sl in Presentation(path).slides: out.append(list(walk(sl.shapes)))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('orig'); ap.add_argument('new')
    a = ap.parse_args()
    za, zb = zipfile.ZipFile(a.orig), zipfile.ZipFile(a.new)
    errs = []
    na, nb = za.namelist(), zb.namelist()
    if set(na) != set(nb): errs.append(f'部件清单不同：多 {sorted(set(nb) - set(na))[:5]} 少 {sorted(set(na) - set(nb))[:5]}')
    same = slides = 0
    for n in na:
        if n not in nb: continue
        da, db = za.read(n), zb.read(n)
        if n.startswith('ppt/theme/') and da != db:
            if canon(da) != canon(db): errs.append(f'{n}：主题里除颜色值外还有改动')
        elif n.startswith('ppt/slides/slide') and n.endswith('.xml'):
            slides += 1
            if canon(da) != canon(db): errs.append(f'{n}：除颜色外还有改动（结构 / 位置 / 文字）')
        elif da == db:
            same += 1
        else:
            errs.append(f'{n}：非幻灯片部件被改动')
    try:
        ta, tb = slide_texts(a.orig), slide_texts(a.new)
        if ta != tb: errs.append('逐页文字不一致')
        chars = sum(len(t) for p in ta for t in p)
    except Exception as e:  # noqa: BLE001
        errs.append(f'python-pptx 打开失败：{e}'); chars = -1
    print('ok' if not errs else 'FAIL', f'slides={slides} other_parts_identical={same} text_chars={chars}')
    for e in errs: print('  !', e)
    sys.exit(1 if errs else 0)


if __name__ == '__main__':
    main()
