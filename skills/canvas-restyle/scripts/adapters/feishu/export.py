#!/usr/bin/env python3
"""第 1 步：导出原画板（只读）并建立本次运行目录。

用法：python3 export.py <画板链接或token> --slug roadmap [--runs-root ./_runs] [--reference <参考画板链接或token>]
产出：<runs-root>/<时间戳>-<slug>/
        source/raw.json  source/preview.jpg              原画板（只读，不要改）
        source/preview.review.jpg                         模型查看副本（最长边 1920px）
        reference/raw.json reference/preview.jpg          参考画板（仅指定 --reference 时）
        reference/preview.review.jpg                      参考画板的模型查看副本
        run.json                                          本次运行元数据（后续步骤读取）
同时打印节点类型统计，供判断画板类型。
"""
import argparse
import collections
import datetime
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wb
from lib import load_raw

REVIEW = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'core', 'review_image.py')


def make_review(path):
    """生成最长边 1920px 的模型查看副本；失败不影响原画板导出。"""
    out = os.path.splitext(path)[0] + '.review' + os.path.splitext(path)[1]
    p = subprocess.run([sys.executable, REVIEW, path, '-o', out], capture_output=True, text=True)
    if p.returncode != 0:
        return None, (p.stderr or p.stdout).strip()[-300:]
    try:
        return json.loads(p.stdout.splitlines()[-1]), None
    except Exception:
        return {'out': out}, None


def summary(raw):
    ns = load_raw(raw)
    c = collections.Counter(n['type'] for n in ns)
    s = collections.Counter((n.get('composite_shape') or {}).get('type') for n in ns if n['type'] == 'composite_shape')
    return {'nodes': len(ns), 'types': dict(c), 'shapes': dict(s),
            'tables': len([n for n in ns if n['type'] == 'table']), 'sections': len([n for n in ns if n['type'] == 'section'])}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('source'); ap.add_argument('--slug', default='board')
    ap.add_argument('--runs-root', default=os.environ.get('WB_RUNS_ROOT', '_runs'))
    ap.add_argument('--reference', help='用户明确指定的参考画板（链接或 token）')
    a = ap.parse_args()
    tok = wb.parse_token(a.source)
    run_dir = os.path.join(a.runs_root, datetime.datetime.now().strftime('%Y-%m-%dT%H%M%S') + '-' + a.slug)
    os.makedirs(os.path.join(run_dir, 'source'), exist_ok=True)
    wb.export(tok, 'raw', os.path.join(run_dir, 'source', 'raw.json'))
    source_preview = os.path.join(run_dir, 'source', 'preview.jpg')
    wb.export(tok, 'preview', source_preview)
    source_review, source_review_warning = make_review(source_preview)
    meta = {'source_token': tok, 'source_input': a.source, 'slug': a.slug, 'created': datetime.datetime.now().isoformat(timespec='seconds'),
            'summary': summary(os.path.join(run_dir, 'source', 'raw.json')),
            'source_review': source_review}
    if source_review_warning: meta['review_warning'] = source_review_warning
    if a.reference:
        rt = wb.parse_token(a.reference)
        os.makedirs(os.path.join(run_dir, 'reference'), exist_ok=True)
        wb.export(rt, 'raw', os.path.join(run_dir, 'reference', 'raw.json'))
        reference_preview = os.path.join(run_dir, 'reference', 'preview.jpg')
        wb.export(rt, 'preview', reference_preview)
        reference_review, reference_review_warning = make_review(reference_preview)
        meta['reference_token'] = rt
        meta['reference_review'] = reference_review
        if reference_review_warning: meta.setdefault('review_warnings', []).append(reference_review_warning)
    json.dump(meta, open(os.path.join(run_dir, 'run.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({'run_dir': run_dir, **meta}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
