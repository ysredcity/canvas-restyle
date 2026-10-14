#!/usr/bin/env python3
"""文字保真校验：比较原画板与新产物的「字符多重集」（忽略空白与换行），差异必须为空。

用法：
  python3 verify_text.py source_raw.json candidate.(svg|json) [--allow "：·"]
candidate 可以是本地 SVG，也可以是写入后导出的线上 raw。
--allow 列出风格文档明确允许删除/新增的字符（如运营看板去掉标签末尾「：」）。
退出码：0 一致；1 有差异。
"""
import argparse
import html
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import list_marker_chars, load_raw, node_text


def norm(s):
    return [c for c in s if not c.isspace()]


def raw_chars(path, markers=False):
    """markers=True 时把原画板富文本列表的序号 / 圆点也计入（重绘会把它们画出来）。"""
    c = Counter()
    for n in load_raw(path):
        for t in node_text(n): c.update(norm(t))
        if markers: c.update(norm(list_marker_chars(n)))
    return c


def svg_chars(path):
    c = Counter()
    for t in re.findall(r'<text[^>]*>(.*?)</text>', open(path).read(), re.S):
        c.update(norm(html.unescape(re.sub(r'<[^>]+>', '', t))))
    return c


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('source'); ap.add_argument('candidate')
    ap.add_argument('--allow', default='', help='允许出现差异的字符')
    a = ap.parse_args()
    cand = svg_chars(a.candidate) if a.candidate.endswith('.svg') else raw_chars(a.candidate)
    src = raw_chars(a.source)
    # 重绘画出了列表序号 / 圆点时，原画板一侧按同一规则计入（比旧版多出的只能是这些符号）
    srcm = raw_chars(a.source, markers=True)
    if srcm != src and not (cand - srcm) and (cand - src):
        src = srcm
    allow = set(a.allow)
    missing = {k: v for k, v in (src - cand).items() if k not in allow}
    extra = {k: v for k, v in (cand - src).items() if k not in allow}
    print(f'source={sum(src.values())} candidate={sum(cand.values())} missing={sum(missing.values())} extra={sum(extra.values())}')
    if missing: print('  缺少:', ''.join(k * v for k, v in sorted(missing.items()))[:200])
    if extra: print('  多出:', ''.join(k * v for k, v in sorted(extra.items()))[:200])
    sys.exit(0 if not missing and not extra else 1)


if __name__ == '__main__':
    main()
