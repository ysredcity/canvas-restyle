"""排版规整（与具体工具无关）：在不改变结构的前提下理顺对齐、间距与尺寸。

输入：同一父容器下的兄弟元素 {id: (x, y, w, h)}（只放「形状」，不放形状里的文字）。
输出：新坐标 {id: (x, y, w, h)} 与改动日志。

保持不变的东西（结构）：元素集合、包含关系、行内左右顺序、行间上下顺序。
会调整的东西（排版）：
  1. 行：上下错位的同行元素顶边对齐，高度相近（±20%）的统一为该行最大高度；
  2. 行距：相邻行之间的空隙统一为中位数；
  3. 列线：左边缘与左边缘、右边缘与右边缘分别聚类并吸附到同一条线（消除 1–8px 的错位），
     容差不超过列距的 0.6 倍，避免把列间距抹平；
  4. 等分：行内连续且宽度相近（±12%）的 ≥3 个元素，在该段首尾之间等宽等距排布；其余元素的边缘优先吸附到这些等分线；
  5. 列距：行内相邻元素的空隙统一为全局中位数（以空隙中点为准）。
位移不设硬上限，只在报告里给出最大位移供参考。
"""
import statistics


def _med(v):
    return statistics.median(v) if v else 0


def rows_of(boxes, ids):
    """按竖直方向重叠聚成行：与行带重叠 ≥ 50%（以较矮者计）即同行。返回 [[id, ...], ...]（自上而下，行内自左向右）。"""
    rows = []
    for i in sorted(ids, key=lambda k: (boxes[k][1], boxes[k][0])):
        x, y, w, h = boxes[i]
        for r in rows:
            top = min(boxes[k][1] for k in r); bot = max(boxes[k][1] + boxes[k][3] for k in r)
            ov = min(bot, y + h) - max(top, y)
            if ov >= 0.5 * min(h, bot - top): r.append(i); break
        else:
            rows.append([i])
    for r in rows: r.sort(key=lambda k: boxes[k][0])
    rows.sort(key=lambda r: min(boxes[k][1] for k in r))
    return rows


def _cluster(vals, tol):
    """一维聚类：返回 {原值: 聚类代表值}。代表值取出现次数最多的值（并列取中位数）。"""
    vs = sorted(vals); groups = []
    for v in vs:
        if groups and v - groups[-1][-1] <= tol: groups[-1].append(v)
        else: groups.append([v])
    out = {}
    for g in groups:
        rounded = [round(v) for v in g]
        best = max(set(rounded), key=lambda r: (rounded.count(r), -abs(r - _med(g))))
        rep = best if rounded.count(best) > 1 else _med(g)
        for v in g: out[v] = rep
    return out


def normalize(boxes, tol=None, gap=None, vgap=None):
    """boxes: {id: [x, y, w, h]}。返回 (new_boxes, info)。"""
    B = {k: list(v) for k, v in boxes.items()}
    if len(B) < 2: return B, {'rows': [list(B)], 'moved': 0, 'max_shift': 0, 'log': []}
    W = max(b[0] + b[2] for b in B.values()) - min(b[0] for b in B.values())
    tol = tol if tol is not None else max(6.0, W * 0.008)
    log = []
    rows = rows_of(B, list(B))

    # 1. 行：顶边对齐、相近高度统一
    for r in rows:
        if len(r) < 2: continue
        top = _med([B[k][1] for k in r]); hs = [B[k][3] for k in r]; hm = _med(hs)
        for k in r:
            if abs(B[k][1] - top) <= tol: B[k][1] = top
        if max(hs) <= hm * 1.2 and min(hs) >= hm * 0.8:
            H = max(hs)
            for k in r: B[k][3] = H

    # 2. 行距统一
    gaps = []
    for a, b in zip(rows, rows[1:]):
        bot = max(B[k][1] + B[k][3] for k in a); top = min(B[k][1] for k in b)
        if top - bot >= 0: gaps.append(top - bot)
    gy = vgap if vgap is not None else (_med(gaps) if gaps else 0)
    if gaps:
        y = None
        for a, b in zip(rows, rows[1:]):
            bot = max(B[k][1] + B[k][3] for k in a); top = min(B[k][1] for k in b)
            cur = top - bot
            if cur < 0 or not (gy * 0.5 <= cur <= gy * 2): continue   # 原本重叠、或间距与主体明显不同（有意的分区留白）的不动
            d = (bot + gy) - cur - bot
            for k in b: B[k][1] += d
            # 后续行随之平移
            idx = rows.index(b)
            for rr in rows[idx + 1:]:
                for k in rr: B[k][1] += d

    # 全局列距：行内相邻元素空隙的中位数（先统计，再吸附；只取窄空隙，排除有意留白）
    hg = [B[b][0] - (B[a][0] + B[a][2]) for r in rows for a, b in zip(r, r[1:])]
    hg = [g for g in hg if 0 <= g <= max(40, W * 0.04)]
    g = gap if gap is not None else (round(_med(hg)) if hg else 8)

    # 3. 列线吸附：左边缘只和左边缘聚类，右边缘只和右边缘聚类（混在一起会把「上一个的右边」
    #    和「下一个的左边」并成一条线，把列间距抹平）。容差不超过列距的 0.6 倍。
    ctol = min(tol, max(2.0, g * 0.6)) if g else tol
    ls = _cluster([B[k][0] for k in B], ctol); rs = _cluster([B[k][0] + B[k][2] for k in B], ctol)
    for k in B:
        nl, nr = ls[B[k][0]], rs[B[k][0] + B[k][2]]
        if nr - nl > 4: B[k][0], B[k][2] = nl, nr - nl

    # 4. 等分：行内「连续且宽度相近」的 ≥3 个元素按等宽等距排布（左侧标签列宽度不同，会被自动排除）
    runs = []
    for r in rows:
        i = 0
        while i < len(r):
            j = i + 1
            while j < len(r):
                seg = r[i:j + 1]; wm = _med([B[k][2] for k in seg])
                if all(abs(B[k][2] - wm) <= wm * 0.12 for k in seg): j += 1
                else: break
            if j - i >= 3: runs.append(r[i:j])
            i = j if j - i >= 3 else i + 1
    fixed = []
    for r in sorted(runs, key=len, reverse=True):
        L = B[r[0]][0]; R = B[r[-1]][0] + B[r[-1]][2]
        # 已有等分线时先吸附首尾
        L = next((f for f in fixed if abs(f - L) <= tol * 2), L); R = next((f for f in fixed if abs(f - R) <= tol * 2), R)
        w = (R - L - g * (len(r) - 1)) / len(r)
        for i, k in enumerate(r):
            B[k][0] = L + i * (w + g); B[k][2] = w
            fixed += [B[k][0], B[k][0] + w]

    # 5. 其他行：边缘吸附等分线，空隙统一
    for r in rows:
        for a, b in zip(r, r[1:]):
            ra, lb = B[a][0] + B[a][2], B[b][0]
            fa = next((f for f in fixed if abs(f - ra) <= tol * 2), None)
            fb = next((f for f in fixed if abs(f - lb) <= tol * 2), None)
            if fa is not None and fb is not None and 0 <= fb - fa <= max(40, W * 0.04):
                B[a][2] = fa - B[a][0]; d = fb - B[b][0]; B[b][0] = fb; B[b][2] -= d
            elif 0 <= lb - ra <= max(40, W * 0.04):
                mid = (ra + lb) / 2
                B[a][2] = mid - g / 2 - B[a][0]; d = (mid + g / 2) - B[b][0]; B[b][0] += d; B[b][2] -= d
        for k in r:
            l, rr = B[k][0], B[k][0] + B[k][2]
            nl = next((f for f in fixed if abs(f - l) <= tol * 2), l); nr = next((f for f in fixed if abs(f - rr) <= tol * 2), rr)
            if nr - nl > 4: B[k][0], B[k][2] = nl, nr - nl

    moved, mx = 0, 0.0
    for k in B:
        s = max(abs(B[k][i] - boxes[k][i]) for i in range(4))
        if s > 0.5: moved += 1; log.append((k, [round(v, 1) for v in boxes[k]], [round(v, 1) for v in B[k]]))
        mx = max(mx, s)
    return B, {'rows': rows, 'gap': g, 'vgap': round(gy, 1), 'tol': round(tol, 1), 'moved': moved,
               'max_shift': round(mx, 1), 'log': log}


def structure_ok(old, new, rows):
    """结构核验：行内左右顺序、行间上下顺序不变，且不新增重叠。返回问题列表。"""
    issues = []
    for r in rows:
        xs = [new[k][0] for k in r]
        if xs != sorted(xs): issues.append(f'行内顺序改变：{r}')
    tops = [min(new[k][1] for k in r) for r in rows]
    if tops != sorted(tops): issues.append('行序改变')

    def ov(a, b):
        return min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]) > 0.5 and min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]) > 0.5
    ks = list(new)
    for i, a in enumerate(ks):
        for b in ks[i + 1:]:
            if ov(new[a], new[b]) and not ov(old[a], old[b]): issues.append(f'新增重叠：{a} / {b}')
    return issues
