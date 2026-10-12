#!/usr/bin/env python3
"""PPT 适配器 · 第 4 步：渲染每页 PNG 供目检（macOS + Microsoft PowerPoint）。

PowerPoint 导出 PDF（受沙盒限制，只能写进它自己的容器目录），再用 pypdfium2 逐页转 PNG。
给了 --compare 原文件时，额外生成「上：原图 / 下：优化版」的对比图，一页只需看一张。

用法：python3 render.py 优化版.pptx -o <目录> [--compare 原文件.pptx] [--scale 1.2]
依赖：pypdfium2、Pillow；本机装有 Microsoft PowerPoint。
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import time

BOX = os.path.expanduser('~/Library/Containers/com.microsoft.Powerpoint/Data/Documents')


def to_pdf(pptx):
    if not os.path.isdir(BOX):
        raise SystemExit('未找到 Microsoft PowerPoint 的容器目录，无法渲染；请手动在 PowerPoint 里打开检查。')
    tag = hashlib.md5(os.path.abspath(pptx).encode()).hexdigest()[:8]
    pdf = os.path.join(BOX, f'canvas-restyle-{tag}.pdf')
    if os.path.exists(pdf): os.remove(pdf)
    src = os.path.abspath(pptx).replace('"', '\\"')
    script = f'''
set outP to (POSIX file "{pdf}") as string
tell application "Microsoft PowerPoint"
  open POSIX file "{src}"
  delay 3
  save active presentation in outP as save as PDF
  delay 1
  close active presentation saving no
end tell'''
    p = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    for _ in range(30):
        if os.path.exists(pdf) and os.path.getsize(pdf) > 0: break
        time.sleep(1)
    if not os.path.exists(pdf):
        raise SystemExit(f'PowerPoint 导出 PDF 失败：{p.stderr.strip()[:300]}')
    return pdf


def to_png(pdf, out_dir, prefix, scale):
    import pypdfium2 as pdfium
    os.makedirs(out_dir, exist_ok=True)
    doc = pdfium.PdfDocument(pdf); paths = []
    for i in range(len(doc)):
        p = os.path.join(out_dir, f'{prefix}-{i + 1:02d}.png')
        doc[i].render(scale=scale).to_pil().save(p); paths.append(p)
    doc.close()
    return paths


def render(pptx, out_dir, prefix, scale):
    pdf = to_pdf(pptx)
    try:
        return to_png(pdf, out_dir, prefix, scale)
    finally:
        shutil.copy(pdf, os.path.join(out_dir, f'{prefix}.pdf')); os.remove(pdf)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pptx'); ap.add_argument('-o', '--out', required=True)
    ap.add_argument('--compare'); ap.add_argument('--scale', type=float, default=1.2)
    a = ap.parse_args()
    new = render(a.pptx, a.out, 'new', a.scale)
    print('\n'.join(new))
    if a.compare:
        from PIL import Image, ImageDraw
        old = render(a.compare, a.out, 'orig', a.scale)
        for i, (o, n) in enumerate(zip(old, new), 1):
            A, B = Image.open(o), Image.open(n); gap = 16
            C = Image.new('RGB', (max(A.width, B.width), A.height + B.height + gap), '#9aa4b2')
            C.paste(A, (0, 0)); C.paste(B, (0, A.height + gap))
            ImageDraw.Draw(C).text((8, A.height + 2), 'ORIGINAL (top) / RESTYLED (bottom)', fill='#ffffff')
            p = os.path.join(a.out, f'compare-{i:02d}.png'); C.save(p); print(p)


if __name__ == '__main__':
    main()
