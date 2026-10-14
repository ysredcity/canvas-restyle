#!/usr/bin/env python3
"""canvas-restyle 统一入口：按输入类型选择适配器，跑完「读取 → 样式方案 → 落地 → 校验」，不发布。

  .pptx 文件            → PPT 适配器：plan → apply → verify → render，产出「<原名>（优化版）.pptx」（当前只改配色）
  飞书画板链接 / token   → 飞书适配器：export → redraw → check → verify_text，产出 diagram.svg（发布另跑 publish.py）
                          默认 standard 档（配色 + 对齐/等距/字号分档/统一字体）；检查不通过自动回退 conservative

用法：python3 restyle.py <输入> --slug demo [--runs-root _runs] [--brand "#00aaa6"|none] [--no-render]
"""
import argparse
import datetime
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PPTX = os.path.join(HERE, 'adapters', 'pptx')
FEISHU = os.path.join(HERE, 'adapters', 'feishu')


def run(cmd, check=True):
    print('$', ' '.join(os.path.basename(c) if i == 1 else c for i, c in enumerate(cmd)))
    p = subprocess.run(cmd, text=True, capture_output=True)
    print((p.stdout or '').rstrip())
    if p.returncode != 0:
        if not check: return p.stdout
        print((p.stderr or '').rstrip()); raise SystemExit(p.returncode)
    return p.stdout


def do_pptx(a):
    stamp = datetime.datetime.now().strftime('%Y-%m-%dT%H%M%S')
    rd = os.path.join(a.runs_root, f'{stamp}-{a.slug}'); os.makedirs(os.path.join(rd, 'source'))
    src = os.path.join(rd, 'source', os.path.basename(a.input)); shutil.copy2(a.input, src)
    stem = os.path.splitext(os.path.basename(a.input))[0]
    out = os.path.join(rd, f'{stem}（优化版）.pptx'); plan = os.path.join(rd, 'plan.json')
    py = sys.executable
    run([py, os.path.join(PPTX, 'plan.py'), src, '-o', plan] + (['--brand', a.brand] if a.brand else []))
    run([py, os.path.join(PPTX, 'apply.py'), src, plan, '-o', out])
    run([py, os.path.join(PPTX, 'verify.py'), src, out])
    if not a.no_render:
        run([py, os.path.join(PPTX, 'render.py'), out, '-o', os.path.join(rd, 'render'), '--compare', src])
    print(f'\n运行目录：{rd}\n优化版：{out}')


def do_feishu(a):
    py = sys.executable
    o = run([py, os.path.join(FEISHU, 'export.py'), a.input, '--slug', a.slug, '--runs-root', a.runs_root])
    import json
    rd = json.loads(o[o.index('{'):]).get('run_dir')
    if not rd: raise SystemExit('export.py 未返回运行目录')
    raw = os.path.join(rd, 'source', 'raw.json'); svg = os.path.join(rd, 'diagram.svg')
    mode = a.mode
    for attempt in (mode, 'conservative'):
        run([py, os.path.join(FEISHU, 'redraw.py'), raw, '-o', svg, '--report', os.path.join(rd, 'report.json'),
             '--mode', attempt] + (['--font', a.font] if a.font else []))
        out = run(['bash', os.path.join(FEISHU, 'check.sh'), svg], check=False)
        if out.startswith('errors=0 warnings=0'):
            mode = attempt; break
        if attempt == 'conservative':
            print('两档都未通过检查，请按 references/adapters/feishu.md「调整」处理'); raise SystemExit(1)
        print(f'! {attempt} 档未通过检查，自动回退到 conservative（只改配色）')
    if not a.no_render: run(['bash', os.path.join(FEISHU, 'check.sh'), svg, '--png'], check=False)
    run([py, os.path.join(FEISHU, 'verify_text.py'), raw, svg])
    print(f'实际使用档位：{mode}')
    print(f'\n运行目录：{rd}\n确认效果后发布：python3 {os.path.join(FEISHU, "publish.py")} {rd} --title "<标题>（配色排版优化版）"')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input'); ap.add_argument('--slug', default='restyle')
    ap.add_argument('--runs-root', default=os.environ.get('WB_RUNS_ROOT', '_runs'))
    ap.add_argument('--brand', help='仅 PPT：品牌色 hex，或 none'); ap.add_argument('--no-render', action='store_true')
    ap.add_argument('--mode', choices=['conservative', 'standard', 'aggressive'], default='standard',
                    help='仅飞书：排版规整档位，默认 standard；检查不通过会自动回退 conservative')
    ap.add_argument('--font', help='仅飞书：统一字体，默认微软雅黑')
    a = ap.parse_args()
    low = a.input.lower()
    if low.endswith('.pptx'):
        if not os.path.isfile(a.input): raise SystemExit(f'找不到文件：{a.input}')
        do_pptx(a)
    elif low.endswith(('.ppt', '.key', '.pps', '.ppsx')):
        raise SystemExit('只支持 .pptx：请先在 PowerPoint / Keynote 里另存为 .pptx。')
    elif low.endswith(('.drawio', '.xml')):
        raise SystemExit('draw.io 适配器尚未实现。')
    else:
        do_feishu(a)


if __name__ == '__main__':
    main()
