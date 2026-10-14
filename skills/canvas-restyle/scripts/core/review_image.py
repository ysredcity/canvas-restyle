#!/usr/bin/env python3
"""生成供多模态模型查看的低分辨率副本；完整原图不变。

默认把最长边缩到 1920px（严格低于部分模型多图请求的 2000px 上限），输出名在扩展名前加 `.review`：
  preview.jpg → preview.review.jpg
  diagram.png → diagram.review.png

长画板需要看局部细节时，另加 `--tiles-dir <目录>`：按原图切成最长边不超过 `--tile-max` 的局部图。
切片用于逐张、分轮查看，不要在同一请求一次发送全部切片。

优先使用 Pillow；macOS 无 Pillow 时，缩略图回退到 sips（切片仍需要 Pillow）。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

DEFAULT_MAX = 1920


def default_out(path):
    stem, ext = os.path.splitext(path)
    return stem + '.review' + ext


def save_pillow(image, path):
    ext = os.path.splitext(path)[1].lower()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if ext in ('.jpg', '.jpeg'):
        if image.mode not in ('RGB', 'L'): image = image.convert('RGB')
        image.save(path, quality=88, optimize=True, progressive=True)
    elif ext == '.png':
        image.save(path, optimize=True)
    elif ext == '.webp':
        image.save(path, quality=88, method=6)
    else:
        image.save(path)


def with_pillow(src, out, limit, tiles_dir=None, tile_max=1920, overlap=80):
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(src)); original = im.size
    review = im.copy(); review.thumbnail((limit, limit), Image.Resampling.LANCZOS)
    save_pillow(review, out)
    tiles = []
    if tiles_dir:
        os.makedirs(tiles_dir, exist_ok=True)
        w, h = im.size
        step = max(1, tile_max - max(0, overlap))
        coords = [(x, y, min(x + tile_max, w), min(y + tile_max, h))
                  for y in range(0, h, step) for x in range(0, w, step)
                  if x < w and y < h]
        # 不为本来就不超限的图片生成没有意义的单张切片。
        if len(coords) > 1:
            ext = os.path.splitext(out)[1].lower() or '.png'
            base = os.path.splitext(os.path.basename(out))[0].replace('.review', '')
            for i, box in enumerate(coords, 1):
                p = os.path.join(tiles_dir, f'{base}.tile-{i:02d}{ext}')
                save_pillow(im.crop(box), p); tiles.append({'path': p, 'box': list(box), 'size': [box[2] - box[0], box[3] - box[1]]})
    return {'engine': 'pillow', 'source': src, 'source_size': list(original), 'out': out,
            'review_size': list(review.size), 'max_dimension': limit, 'tiles': tiles}


def with_sips(src, out, limit):
    if sys.platform != 'darwin' or shutil.which('sips') is None:
        raise RuntimeError('未安装 Pillow，且当前系统没有 sips')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    p = subprocess.run(['sips', '-Z', str(limit), src, '--out', out], capture_output=True, text=True)
    if p.returncode != 0: raise RuntimeError((p.stderr or p.stdout).strip()[-300:])
    q = subprocess.run(['sips', '-g', 'pixelWidth', '-g', 'pixelHeight', out], capture_output=True, text=True)
    vals = {}
    for line in q.stdout.splitlines():
        if ':' in line:
            k, v = line.strip().split(':', 1)
            if v.strip().isdigit(): vals[k] = int(v.strip())
    size = [vals.get('pixelWidth'), vals.get('pixelHeight')]
    return {'engine': 'sips', 'source': src, 'source_size': None, 'out': out,
            'review_size': size, 'max_dimension': limit, 'tiles': []}


def create(src, out=None, limit=DEFAULT_MAX, tiles_dir=None, tile_max=1920, overlap=80):
    if not os.path.isfile(src): raise FileNotFoundError(src)
    if limit >= 2000: raise ValueError('--max 必须小于 2000；推荐 1920')
    if tile_max >= 2000: raise ValueError('--tile-max 必须小于 2000；推荐 1920')
    out = out or default_out(src)
    try:
        return with_pillow(src, out, limit, tiles_dir, tile_max, overlap)
    except ImportError:
        if tiles_dir: raise RuntimeError('生成局部切片需要 Pillow；请安装 Pillow，或省略 --tiles-dir')
        return with_sips(src, out, limit)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('image'); ap.add_argument('-o', '--out')
    ap.add_argument('--max', type=int, default=DEFAULT_MAX, help='review 最长边，必须 <2000（默认 1920）')
    ap.add_argument('--tiles-dir', help='可选：长画板的局部切片目录；切片请逐张分轮查看')
    ap.add_argument('--tile-max', type=int, default=1920, help='切片边长上限，必须 <2000')
    ap.add_argument('--overlap', type=int, default=80, help='切片重叠像素，默认 80')
    a = ap.parse_args()
    try:
        result = create(a.image, a.out, a.max, a.tiles_dir, a.tile_max, a.overlap)
    except Exception as e:
        print(f'review image 生成失败：{e}', file=sys.stderr); return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
