"""「运营」看板 · 版式基准模板（v1）。数据段为虚构示例，仅用于演示版式。
用法：复制到运行目录，只替换「数据」段（TITLE/HEADS/VALUES/BENCH/PROBLEMS/PLANS/PILLARS/FOOTER），
版式常量与配色保持不变；规范见 references/styles/ops-board.md。运行后输出 diagram.svg。"""

# ======================= 数据（只改这里；以下为虚构示例） =======================
TITLE = "示例服务运营"
# 业务主线：5 列（标题, 副标题）；前 4 列为流程（列间 › 箭头），第 5 列为贯穿项（以 + 连接，靛蓝色）
HEADS = [("① 交付实施（系统A）", "实施期·方案部署→交付期·验收上线"),
         ("② 质保服务（系统B）", "质保期内的维护保养"),
         ("③ 增值服务(系统C-线下)", "商机来源：客服中心、交付及其他渠道"),
         ("④ 升级换新（系统A）", "质保外运营期·升级焕新"),
         ("配件产品（系统C）", "贯穿全周期配件耗材需求")]
# 价值呈现：每列一组行（原图有硬换行就拆成多行）
VALUES = [["① 方案合理·周期可控；", "验收达标"], ["② 响应及时·少停机·快速处置"], ["③省心·降本·提效,品质可靠"],
          ["④ 旧设备焕新·节能降本·提体验"], ["正品保障·及时交付"]]
# 对标：导语 + （粗体前缀, 正文）条目，通栏
BENCH = ('行业标杆依托 "自营服务网络 + 专业实施体系 + 配件经营" 三线协同布局：',
         [("增值服务：", '依托 50 家自营服务网点，重点推进 "远程监控、预测性维护、能耗管理"，把存量客户长期留在自有体系内；'),
          ("升级换新：", "依托 10 家区域实施中心，抓住存量设备更替窗口期，强化专业实施能力，提升品牌价值；"),
          ("配件经营：", "推进配件商品化、标准化建设，深挖客户需求，实现业务收入增长。")])
# 现状及问题：主卡（跨前 3 列：粗体导语 + 圆点条目）+ 第 4、5 列各一段
PROBLEMS = (("系统A、系统B、系统C 三套系统彼此割裂，数据不联动，造成：",
             ["存量项目与客服中心识别的需求难以转化为服务商机；", "无法支撑以项目为中心的全周期运营、数据分析和沉淀。"]),
            ["增值服务履约在线下进行，过程质量管控弱", "配件价格管理、退换货处理多个环节依赖人工，系统功能尚未贯通"])
# 现状主卡底部的补充标签（原图有补充说明时填写，否则 None）
PROBLEM_NOTE = None
# 规划方向：主卡（跨前 3 列，手动分行）+ 第 4、5 列各一段；下方 2×2 支撑项（标签, 说明）
PLANS = (["打通商机来源，整合系统A、B、C 功能，完成各业务环节数据联动，",
          "建设全周期服务运营平台，动态管理项目状态，实现全周期运营闭环和用户沉淀"],
         ["实现增值与换新履约线上化，建立服务质量评价体系", "拉通各业务系统，实现配件价格自动发布和退货线上化"])
PILLARS = [[("平台赋能", "运营平台上线 可视·商机追踪"), ("团队标准化", "专职团队·SOP 激励与质量评价机制落地")],
           [("服务渠道", "服务站 30 家 实施服务中心 200 家"), ("数字化+AI", "预测维护    智能派单（覆盖≥50%）")]]
# 底栏：目标标签 + 分段（文字, 是否高亮）；底盘标签 + 文字
FOOTER = ("年度目标", [("服务收入实现", False), ("X 亿元", True), ("（增长 50%）", False)],
          "存量底盘", "工程项目 4 万+｜配套社区 6000+｜家庭用户 400 万户｜服务渠道 3000+")
# 业务主线中参与流程的列数：4 = 前 4 列 › 相连 + 第 5 列贯穿项；5 = 5 列全部 › 相连
HEAD_FLOW = 4
# ---- 按列变体（行 key 带 _cols；不用时保持 None）----
BENCH_COLS = None     # (首列标签如"标杆"或None, [每列行列表 x5])
PROBLEMS_COLS = None  # [每列 [(问题标题, 说明), ...] x5]
PLANS_COLS = None     # [每列 (标题, 副标题) x5]
FOOTER_GOALS = None   # (目标标签, [标语短语...], [子目标...])；设置后替代 FOOTER
# 行序（与原画板一致；可调整顺序，不可增删行类型）。按列变体用 bench_cols / problems_cols / plans_cols
ORDER = ["heads", "values", "bench", "problems", "plans"]

# ======================= 版式（不要改） =======================
F = 'font-family="Noto Sans SC"'
o = []; a = o.append
def esc(t): return t.replace('&', '&amp;').replace('<', '&lt;')
def cw(ch, fs): return fs * (1 if ord(ch) > 255 else 0.56)
def tw(t, fs): return sum(cw(ch, fs) for ch in t)
def wrap(t, w, fs):
    L = []; cur = ''; c = 0
    for ch in t:
        k = cw(ch, fs)
        if c + k > w and cur: L.append(cur); cur = ''; c = 0
        cur += ch; c += k
    if cur: L.append(cur)
    return L
def bwrap(t, w, fs):
    """均衡换行：行数不变，各行长度尽量相近，避免末行孤字。"""
    L = wrap(t, w, fs)
    if len(L) < 2: return L
    tot = tw(t, fs); n = len(L); ww = tot / n
    while True:
        M = wrap(t, ww, fs)
        if len(M) <= n: return M
        ww += fs * 0.5
def T(x, y, t, fs=14, fill="#1f2937", w="normal", anchor="middle"):
    a(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{fs}" {F} font-weight="{w}" fill="{fill}" text-anchor="{anchor}">{esc(t)}</text>')
def ML(cx, cy, lines, fs, fill, w="normal", lh=None, anchor="middle"):
    lh = lh or fs * 1.5; n = len(lines); y0 = cy - (n - 1) * lh / 2 + fs * 0.36
    for i, l in enumerate(lines): T(cx, y0 + i * lh, l, fs, fill, w, anchor)
def R(x, y, w, h, fill, stroke=None, rx=10, sw=1, sh=False):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ''
    f = ' filter="url(#sh)"' if sh else ''
    a(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"{s}{f}/>')

W = 1560; LX, LW = 40, 112
CX = [164, 436, 708, 980, 1252]; CW = 260; RIGHT = 1512
S3 = (164, 804)                     # 跨前 3 列的主卡
GAP = 12
body = []                            # 先收集主体，最后加头部（需要总高度）
def label(y, h, t, col, bg):
    R(LX, y, LW, h, bg, None, 10, 1, True); a(f'<rect x="{LX}" y="{y}" width="5" height="{h}" rx="2.5" fill="{col}"/>')
    ML(LX + LW / 2 + 2, y + h / 2, [t], 16, col, "bold")
def card(x, y, w, h, bg, bar, stroke):
    R(x, y, w, h, bg, stroke, 10, 1, True); a(f'<rect x="{x+10}" y="{y}" width="{w-20}" height="3" rx="1.5" fill="{bar}"/>')

def row_heads(y):
    h = 76
    label(y, h, "业务主线", "#0f766e", "#e3f2ef")
    for i, (t, s) in enumerate(HEADS):
        x = CX[i]; five = i >= HEAD_FLOW
        R(x, y, CW, h, "url(#hd5)" if five else "url(#hd)", "#c9cff0" if five else "#b9ddd6", 10, 1, True)
        T(x + CW / 2, y + 31, t, 17, "#3b3f8f" if five else "#0f5f5a", "bold")
        T(x + CW / 2, y + 56, s, 12.5, "#4b5563")
    ym = y + h / 2
    for i in range(HEAD_FLOW - 1):
        xm = CX[i] + CW + 6
        a(f'<circle cx="{xm}" cy="{ym}" r="9" fill="#ffffff" stroke="#14b8a6" stroke-width="1.2"/>')
        a(f'<path d="M{xm-3},{ym-4} L{xm+2.5},{ym} L{xm-3},{ym+4}" fill="none" stroke="#0f766e" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>')
    if HEAD_FLOW < 5:
        xm = CX[HEAD_FLOW - 1] + CW + 6
        a(f'<circle cx="{xm}" cy="{ym}" r="9" fill="#ffffff" stroke="#6366f1" stroke-width="1.2"/>')
        a(f'<path d="M{xm-4},{ym} H{xm+4} M{xm},{ym-4} V{ym+4}" stroke="#4f46e5" stroke-width="1.8" stroke-linecap="round"/>')
    return h

def row_values(y):
    h = 76
    label(y, h, "价值呈现", "#15803d", "#e6f4ea")
    for i, v in enumerate(VALUES):
        card(CX[i], y, CW, h, "#f3faf5", "#4ade80", "#cfe9d7")
        ML(CX[i] + CW / 2, y + h / 2 + 2, v, 14.5, "#14532d", "normal", 22)
    return h

def row_bench(y):
    lead, items = BENCH
    h = 62 + (len(items) - 1) * 24 + 14
    label(y, h, "对标", "#0e7490", "#e2f1f5")
    card(164, y, RIGHT - 164, h, "#f5fafc", "#38bdf8", "#cfe3ec")
    T(188, y + 32, lead, 14.5, "#0c4a6e", "bold", "start")
    for k, (b, t) in enumerate(items):
        yy = y + 62 + k * 24
        a(f'<circle cx="204" cy="{yy-5}" r="3" fill="#0ea5e9"/>')
        T(214, yy, b, 14, "#0c4a6e", "bold", "start"); T(214 + tw(b, 14) + 2, yy, t, 14, "#374151", "normal", "start")
    return h

def row_problems(y):
    (lead, bullets), sides = PROBLEMS
    side_lines = [wrap(t, CW - 36, 14.5) for t in sides]
    h = max(124, 68 + len(bullets) * 28 + (44 if PROBLEM_NOTE else 0), 36 + max(len(L) for L in side_lines) * 24 + 16)
    label(y, h, "现状及问题", "#b45309", "#fbf0e1")
    card(S3[0], y, S3[1], h, "#fffaf2", "#f59e0b", "#f1dcbc")
    px = S3[0] + 24
    T(px, y + 36, lead, 14.5, "#7c2d12", "bold", "start")
    for k, t in enumerate(bullets):
        yy = y + 68 + k * 28
        a(f'<circle cx="{px+8}" cy="{yy-5}" r="3" fill="#f59e0b"/>'); T(px + 20, yy, t, 14, "#374151", "normal", "start")
    if PROBLEM_NOTE:
        yn = y + 68 + len(bullets) * 28 - 6
        a(f'<line x1="{px}" y1="{yn}" x2="{S3[0]+S3[1]-24}" y2="{yn}" stroke="#f1dcbc" stroke-dasharray="4 4"/>')
        nw = tw(PROBLEM_NOTE, 12.5) + 24
        R(px, yn + 12, round(nw), 24, "#fdebd3", "#f3c58f", 12); T(px + nw / 2, yn + 29, PROBLEM_NOTE, 12.5, "#9a3412", "bold")
    for i, L in zip((3, 4), side_lines):
        card(CX[i], y, CW, h, "#fffaf2", "#f59e0b", "#f1dcbc")
        for k, l in enumerate(L): T(CX[i] + 18, y + 36 + k * 24, l, 14.5, "#374151", "normal", "start")
    return h

def row_plans(y):
    main, sides = PLANS
    ha, hb, g = 64, 52, 10
    h = ha + (hb + g) * len(PILLARS)
    label(y, h, "规划方向", "#1d4ed8", "#e6eefb")
    for x, w, L in [(S3[0], S3[1], main)] + [(CX[i], CW, wrap(t, CW - 36, 14)) for i, t in zip((3, 4), sides)]:
        card(x, y, w, ha, "#f2faf4", "#4ade80", "#cfe9d7")
        ML(x + w / 2, y + ha / 2 + 2, L, 14, "#14532d", "normal", 21)
    half = (RIGHT - 164 - 12) / 2
    for r, pair in enumerate(PILLARS):
        yy = y + ha + g + r * (hb + g)
        for c, (k, v) in enumerate(pair):
            x = 164 + c * (half + 12)
            R(x, yy, half, hb, "#ffffff", "#cdd9f0", 10, 1, True)
            a(f'<rect x="{x}" y="{yy}" width="4" height="{hb}" rx="2" fill="#3b82f6"/>')
            kw = tw(k, 13) + 20
            a(f'<rect x="{x+18}" y="{yy+14}" width="{kw:.0f}" height="24" rx="12" fill="#dbe7ff"/>')
            T(x + 18 + kw / 2, yy + 31, k, 13, "#1e3a8a", "bold")
            T(x + 18 + kw + 14, yy + 31, v, 14.5, "#1f2937", "normal", "start")
    return h

def footer(y):
    hf = 48; tag1, segs, tag2, base = FOOTER
    R(LX, y, RIGHT - LX, hf, "url(#ft)", None, 12, 1, True)
    w1 = round(tw(tag1, 13.5) + 40)
    R(LX + 12, y + 10, round(w1), 28, "#facc15", None, 14); T(LX + 12 + w1 / 2, y + 29, tag1, 13.5, "#713f12", "bold")
    x0 = LX + 12 + w1 + 14
    for seg, hi in segs:
        T(x0, y + 30, seg, 15, "#fde68a" if hi else "#ffffff", "bold" if hi else "normal", "start"); x0 += tw(seg, 15) + 2
    a(f'<line x1="560" y1="{y+12}" x2="560" y2="{y+36}" stroke="#7dd3c0" stroke-width="1"/>')
    w2 = tw(tag2, 13.5) + 28
    R(580, y + 10, round(w2), 28, "#ccfbf1", None, 14); T(580 + w2 / 2, y + 29, tag2, 13.5, "#0f5f5a", "bold")
    T(580 + w2 + 14, y + 30, base, 14.5, "#ffffff", "normal", "start")
    return hf

def row_bench_cols(y):
    tag, cols = BENCH_COLS
    fs, lh = 13.5, 20
    cells = []
    for i, lines in enumerate(cols):
        tagw = (tw(tag, 13) + 16) if (tag and i == 0) else 0
        w = CW - 32 - (tagw + 10 if tagw else 0)
        L = [l2 for l in lines for l2 in wrap(l, w, fs)]
        cells.append((tagw, L))
    h = max(64, max(len(L) for _, L in cells) * lh + 30)
    label(y, h, "对标", "#0e7490", "#e2f1f5")
    card(164, y, RIGHT - 164, h, "#f5fafc", "#38bdf8", "#cfe3ec")
    for i, (tagw, L) in enumerate(cells):
        x = CX[i]
        if i: a(f'<line x1="{x-6}" y1="{y+14}" x2="{x-6}" y2="{y+h-14}" stroke="#cfe3ec" stroke-width="1" stroke-dasharray="4 4"/>')
        cy = y + h / 2 + 2
        if tagw:
            R(x + 16, cy - 12, round(tagw), 24, "#0e7490", None, 6); T(x + 16 + tagw / 2, cy + 4.5, tag, 13, "#ffffff", "bold")
            ML(x + 16 + tagw + 10, cy, L, fs, "#0c4a6e", "normal", lh, "start")
        else:
            ML(x + CW / 2, cy, L, fs, "#0c4a6e", "normal", lh)
    return h

def row_problems_cols(y):
    tfs, dfs, tlh, dlh, gap = 14.5, 13.5, 21, 21, 14
    lay = []
    for items in PROBLEMS_COLS:
        blocks = [(bwrap(t, CW - 64, tfs), wrap(d, CW - 36, dfs)) for t, d in items]
        hh = sum(len(tl) * tlh + 6 + len(dl) * dlh for tl, dl in blocks) + gap * (len(blocks) - 1)
        lay.append((blocks, hh))
    h = max(124, max(hh for _, hh in lay) + 44)
    label(y, h, "现状及问题", "#b45309", "#fbf0e1")
    for i, (blocks, _) in enumerate(lay):
        x = CX[i]
        card(x, y, CW, h, "#fffaf2", "#f59e0b", "#f1dcbc")
        yy = y + 32
        for k, (tl, dl) in enumerate(blocks):
            if k: a(f'<line x1="{x+18}" y1="{yy-gap/2-6}" x2="{x+CW-18}" y2="{yy-gap/2-6}" stroke="#f1dcbc" stroke-width="1" stroke-dasharray="3 3"/>')
            a(f'<circle cx="{x+22}" cy="{yy-5}" r="3" fill="#f59e0b"/>')
            for j, l in enumerate(tl): T(x + 32, yy + j * tlh, l, tfs, "#7c2d12", "bold", "start")
            yy += len(tl) * tlh + 6
            for j, l in enumerate(dl): T(x + 18, yy + j * dlh, l, dfs, "#374151", "normal", "start")
            yy += len(dl) * dlh + gap
    return h

def row_plans_cols(y):
    lay = [(bwrap(t, CW - 28, 15), bwrap(s2, CW - 28, 13)) for t, s2 in PLANS_COLS]
    h = max(76, max(len(t) * 22 + len(s2) * 19 for t, s2 in lay) + 38)
    label(y, h, "规划方向", "#1d4ed8", "#e6eefb")
    for i, (tl, sl) in enumerate(lay):
        x = CX[i]
        card(x, y, CW, h, "#f2faf4", "#4ade80", "#cfe9d7")
        tot = len(tl) * 22 + 6 + len(sl) * 19
        yy = y + (h - tot) / 2 + 17
        for j, l in enumerate(tl): T(x + CW / 2, yy + j * 22, l, 15, "#14532d", "bold")
        yy += len(tl) * 22 + 6
        for j, l in enumerate(sl): T(x + CW / 2, yy + j * 19, l, 13, "#15803d")
    return h

def footer_goals(y):
    tag, heads, subs = FOOTER_GOALS
    hf = 88
    R(LX, y, RIGHT - LX, hf, "url(#ft)", None, 12, 1, True)
    w1 = round(tw(tag, 14) + 32)
    R(LX + 16, y + hf / 2 - 15, w1, 30, "#facc15", None, 15); T(LX + 16 + w1 / 2, y + hf / 2 + 5, tag, 14, "#713f12", "bold")
    x0 = LX + 16 + w1 + 24
    xs = x0
    for k, p in enumerate(heads):
        T(xs, y + 34, p, 17, "#ffffff", "bold", "start"); xs += tw(p, 17) + 30
    xs = x0
    for p in subs:
        pw = round(tw(p, 13.5) + 28)
        R(xs, y + 50, pw, 26, "#ccfbf1", None, 13); T(xs + pw / 2, y + 67.5, p, 13.5, "#0f5f5a", "bold"); xs += pw + 12
    return hf

ROWS = {"heads": row_heads, "values": row_values, "bench": row_bench, "problems": row_problems, "plans": row_plans,
        "bench_cols": row_bench_cols, "problems_cols": row_problems_cols, "plans_cols": row_plans_cols}
y = 96
for k in ORDER:
    y += ROWS[k](y) + GAP
y += footer_goals(y) if FOOTER_GOALS else footer(y)
body, o = o, []; a = o.append
H = y + 36
a(f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
<linearGradient id="hd" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#e6f4f1"/><stop offset="1" stop-color="#d3ece7"/></linearGradient>
<linearGradient id="hd5" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#eef0fb"/><stop offset="1" stop-color="#e0e5f7"/></linearGradient>
<linearGradient id="ft" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#0f5f5a"/><stop offset="1" stop-color="#16867c"/></linearGradient>
<filter id="sh" filterUnits="userSpaceOnUse" x="-50" y="-50" width="{W+140}" height="{H+140}"><feDropShadow dx="0" dy="2" stdDeviation="4" flood-color="#0f3d3a" flood-opacity="0.08"/></filter>
</defs>
<rect width="{W}" height="{H}" fill="#f6f9f9"/>''')
T(W / 2, 58, TITLE, 30, "#0f5f5a", "bold")
a(f'<rect x="{W/2-36}" y="70" width="72" height="4" rx="2" fill="#14b8a6"/>')
o += body
a('</svg>')
open('diagram.svg', 'w').write('\n'.join(o))
print('height', H)
