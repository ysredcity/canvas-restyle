"""lark-cli 调用封装：解析画板链接、导出、建文档、写入。被 export.py / publish.py 共用。"""
import json
import re
import subprocess
import urllib.parse


def parse_token(s):
    """从飞书链接或裸 token 中取画板 token。
    支持：…?blockToken=XXX&blockType=whiteboard…、/board/XXX、/whiteboard/XXX、裸 token。"""
    s = s.strip()
    if re.fullmatch(r'[A-Za-z0-9]{20,40}', s): return s
    q = urllib.parse.parse_qs(urllib.parse.urlparse(s).query)
    if q.get('blockToken') and (q.get('blockType', ['whiteboard'])[0] == 'whiteboard'): return q['blockToken'][0]
    m = re.search(r'/(?:board|whiteboard)/([A-Za-z0-9]{20,40})', s)
    if m: return m.group(1)
    raise SystemExit(f'无法从输入中解析画板 token：{s[:80]}…\n'
                     '若是文档 / wiki 链接且未带 blockToken，请先在飞书里点开画板复制带 blockToken 的链接，'
                     '或用 lark-cli docs +fetch 找到画板块的 token。')


def run(args, check=True):
    p = subprocess.run(['lark-cli'] + args, capture_output=True, text=True)
    if check and p.returncode != 0:
        raise SystemExit(f'lark-cli {" ".join(args[:3])} 失败：\n{(p.stderr or p.stdout)[-800:]}')
    return p.stdout


def export(token, kind, out):
    run(['whiteboard', '+export', '--whiteboard-token', token, '--output-type', kind,
         '--output', out, '--overwrite', '--as', 'user'])


def create_doc(title, parent=None):
    args = ['docs', '+create', '--title', title, '--content', '<whiteboard type="blank"></whiteboard>', '--as', 'user']
    if parent: args += ['--parent-token', parent]
    d = json.loads(run(args))['data']['document']
    wb = next(b for b in d['new_blocks'] if b['block_type'] == 'whiteboard')
    return d['url'], wb['block_token'], d['document_id']


def update(token, svg_path, idem):
    out = run(['whiteboard', '+update', '--whiteboard-token', token, '--input_format', 'svg',
               '--source', '@' + svg_path, '--overwrite', '--idempotent-token', idem, '--as', 'user'])
    if '"ok": true' not in out: raise SystemExit('写入画板失败：\n' + out[-800:])
