"""字号分档与统一字体（与具体工具无关）。

字号分档：把原图里零散的字号聚成 3–4 档（标题 / 小标题 / 正文 / 辅助），同一档统一取一个值。
只合并差距在 ±15% 以内的字号；差距大的档位一律保持区分，宁可超出档数上限，也不把正文并进标题。

统一字体：默认优先「微软雅黑」，用户可指定；找不到时按候选列表回退。
"""
import statistics

# 中文优先字体候选；飞书画板导入时用 whiteboard-cli 自带 Noto Sans SC 渲染，PPT 由系统字体渲染。
FONT_PREFS = ['微软雅黑', 'Microsoft YaHei', 'PingFang SC', 'Noto Sans SC', 'Source Han Sans SC', 'Arial']

# 档位名与建议值（相对正文的比例，仅在原图字号缺失时兜底）
TIERS = ('title', 'subtitle', 'body', 'caption')


def tier_sizes(sizes, tol=0.15, max_tiers=4):
    """sizes: 画板里出现的全部字号（可重复，重复次数代表权重）。
    返回 {原字号: 规整后字号}。相邻字号差距在 tol 以内才合并，合并值取该组里出现最多的字号。"""
    if not sizes: return {}
    uniq = sorted(set(sizes))
    groups = [[uniq[0]]]
    for s in uniq[1:]:
        if s <= groups[-1][0] * (1 + tol): groups[-1].append(s)   # 与组内最小值比，避免逐级串联把正文并进标题
        else: groups.append([s])
    # 档数超限时合并差距最小的相邻两组；但只合并本身就在 tol 以内的，差距大的档位宁可多留一档
    while len(groups) > max_tiers:
        i = min(range(len(groups) - 1), key=lambda j: groups[j + 1][0] / groups[j][-1])
        if groups[i + 1][0] / groups[i][-1] > 1 + tol: break
        groups[i] += groups.pop(i + 1)
    out = {}
    for g in groups:
        rep = max(g, key=lambda s: (sizes.count(s), s))
        for s in g: out[s] = rep
    return out


def pick_font(user=None, available=None):
    """选统一字体：用户指定优先；否则按 FONT_PREFS 取第一个可用；都不可用时返回首选名。
    available 为 None 表示不校验可用性（飞书 SVG 场景由渲染端兜底）。"""
    prefs = ([user] if user else []) + FONT_PREFS
    if not available: return prefs[0]
    low = {a.lower(): a for a in available}
    for p in prefs:
        if p.lower() in low: return low[p.lower()]
    return prefs[0]


def report(mapping, sizes):
    """字号分档报告：每档的原字号与合并后的值、涉及的文字数量。"""
    tiers = {}
    for s, t in mapping.items():
        tiers.setdefault(t, {'from': [], 'count': 0})
        tiers[t]['from'].append(s); tiers[t]['count'] += sizes.count(s)
    for t in tiers: tiers[t]['from'] = sorted(tiers[t]['from'])
    return {str(k): v for k, v in sorted(tiers.items(), key=lambda kv: -kv[0])}


def median(v):
    return statistics.median(v) if v else 0
