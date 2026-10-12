#!/usr/bin/env python3
"""第 1 步：导出原画板（只读）并建立本次运行目录。

用法：python3 export.py <画板链接或token> --slug roadmap [--runs-root ./_runs] [--reference <参考画板链接或token>]
产出：<runs-root>/<时间戳>-<slug>/
        source/raw.json  source/preview.jpg      原画板（只读，不要改）
        reference/raw.json reference/preview.jpg 参考画板（仅指定 --reference 时）
        run.json                                  本次运行元数据（后续步骤读取）
同时打印节点类型统计，供判断画板类型。
"""
import argparse
import collections
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wb
from lib import load_raw


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
    wb.export(tok, 'preview', os.path.join(run_dir, 'source', 'preview.jpg'))
    meta = {'source_token': tok, 'source_input': a.source, 'slug': a.slug, 'created': datetime.datetime.now().isoformat(timespec='seconds'),
            'summary': summary(os.path.join(run_dir, 'source', 'raw.json'))}
    if a.reference:
        rt = wb.parse_token(a.reference)
        os.makedirs(os.path.join(run_dir, 'reference'), exist_ok=True)
        wb.export(rt, 'raw', os.path.join(run_dir, 'reference', 'raw.json'))
        wb.export(rt, 'preview', os.path.join(run_dir, 'reference', 'preview.jpg'))
        meta['reference_token'] = rt
    json.dump(meta, open(os.path.join(run_dir, 'run.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({'run_dir': run_dir, **meta}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
