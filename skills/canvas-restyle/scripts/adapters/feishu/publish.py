#!/usr/bin/env python3
"""最后一步：本地校验 → 新建飞书文档（含空白画板）→ 写入 → 导出线上 raw 复核 → 登记到运行注册表。

用法：python3 publish.py <run_dir> --title "XX（配色排版优化版）" [--svg diagram.svg] [--allow "："] [--parent-token X]
安全约束：
  - 只写入本次新建的画板；若目标 token 与原画板 / 参考画板相同，立即中止。
  - 本地 --check 或文字比对未通过时不写入（--force 可跳过检查，但会在报告中标注）。
"""
import argparse
import datetime
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import wb
from lib import load_raw


def sh(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('run_dir'); ap.add_argument('--title', required=True)
    ap.add_argument('--svg', default='diagram.svg'); ap.add_argument('--allow', default='')
    ap.add_argument('--parent-token'); ap.add_argument('--force', action='store_true')
    ap.add_argument('--engine', default='redraw', help='redraw / template:<name> / script')
    a = ap.parse_args()
    rd = a.run_dir; meta = json.load(open(os.path.join(rd, 'run.json')))
    svg = os.path.join(rd, a.svg); src_raw = os.path.join(rd, 'source', 'raw.json')

    rc1, chk = sh(['bash', os.path.join(HERE, 'check.sh'), svg])
    rc2, txt = sh([sys.executable, os.path.join(HERE, 'verify_text.py'), src_raw, svg, '--allow', a.allow])
    print('本地检查：', chk.splitlines()[0] if chk else chk); print('文字比对：', txt.splitlines()[0] if txt else txt)
    if (rc1 or rc2) and not a.force:
        print(chk); print(txt); raise SystemExit('本地校验未通过，未写入。修复后重试，或确认后加 --force。')

    url, token, doc_id = wb.create_doc(a.title, a.parent_token)
    if token in (meta.get('source_token'), meta.get('reference_token')):
        raise SystemExit('目标画板与原画板/参考画板相同，已中止。')
    idem = datetime.datetime.now().strftime('%Y%m%d%H%M%S') + '-' + meta.get('slug', 'board')
    wb.update(token, svg, idem)
    online = os.path.join(rd, 'online.json')
    wb.export(token, 'raw', online)
    rc3, txt2 = sh([sys.executable, os.path.join(HERE, 'verify_text.py'), src_raw, online, '--allow', a.allow])
    nodes = len(load_raw(online))

    meta.update({'published': datetime.datetime.now().isoformat(timespec='seconds'), 'title': a.title, 'doc_url': url,
                 'whiteboard_token': token, 'engine': a.engine, 'online_nodes': nodes,
                 'online_text_check': txt2.splitlines()[0] if txt2 else '', 'forced': a.force})
    json.dump(meta, open(os.path.join(rd, 'run.json'), 'w'), ensure_ascii=False, indent=1)
    reg_path = os.path.join(os.path.dirname(os.path.abspath(rd)), 'registry.json')
    reg = json.load(open(reg_path)) if os.path.exists(reg_path) else {'_note': '本地运行注册表：优化后画板 token → 运行目录。参考模式会先查这里。', 'boards': {}}
    reg['boards'][token] = {'title': a.title, 'doc_url': url, 'source_token': meta['source_token'],
                            'run_dir': os.path.relpath(rd, os.path.dirname(reg_path)), 'engine': a.engine,
                            'date': meta['published'][:10]}
    json.dump(reg, open(reg_path, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({'doc_url': url, 'whiteboard_token': token, 'online_nodes': nodes,
                      'online_text_check': meta['online_text_check'], 'registry': reg_path}, ensure_ascii=False, indent=1))
    if rc3: print('⚠ 线上文字与原图存在差异（可能是线上把长文本拆段，需抽查）：\n' + txt2)


if __name__ == '__main__':
    main()
