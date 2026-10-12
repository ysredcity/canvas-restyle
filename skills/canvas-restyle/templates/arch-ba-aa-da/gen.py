"""BA/AA/DA 架构差距图 · 版式基准模板（v2）。数据段为虚构示例，仅用于演示版式。
用法：复制到运行目录，只替换「数据」段（JOURNEY/VALUE/BA/AA/DA_L/DA_R/LEGEND），
版式常量与配色保持不变；规范见 references/styles/ba-aa-da.md。运行后输出 diagram.svg。"""
from PIL import ImageFont
import glob as _glob, os as _os
FD = _os.environ.get('WB_FONT_DIR') or next(iter(sorted(_glob.glob(_os.path.expanduser('~/.npm/_npx/*/node_modules/@larksuite/whiteboard-cli/dist/fonts')))), '')
FD = FD.rstrip('/') + '/'   # 文字宽度用 whiteboard-cli 自带 Noto Sans SC 实测；首次需先跑一次 npx whiteboard-cli
_fc = {}
def font(size, bold):
    k = (size, bold)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(FD + ('NotoSansSC-Bold.ttf' if bold else 'NotoSansSC-Regular.ttf'), int(size * 10))
    return _fc[k]
def tw(t, size, bold=False):
    return font(size, bold).getlength(t) / 10.0

F = 'font-family="Noto Sans SC"'
o = []
a = o.append
def esc(t): return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
def T(x, y, t, fs=15, fill="#2d3748", w="normal", anchor="middle"):
    a(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{fs}" {F} font-weight="{w}" fill="{fill}" text-anchor="{anchor}">{esc(t)}</text>')
def TC(cx, cy, t, fs=15, fill="#2d3748", w="normal"):
    T(cx, cy + fs * 0.36, t, fs, fill, w)
def R(x, y, w, h, fill, stroke=None, rx=10, sw=1, sh=False):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ''
    f = ' filter="url(#sh)"' if sh else ''
    a(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}"{s}{f}/>')
def chev(x, y, w, h, d, fill, stroke=None, flat=False, sw=1):
    pts = [(x, y), (x + w - d, y), (x + w, y + h / 2), (x + w - d, y + h), (x, y + h)]
    if not flat:
        pts.append((x + d, y + h / 2))
    s = f' stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round"' if stroke else ''
    a('<polygon points="' + ' '.join(f'{px:.1f},{py:.1f}' for px, py in pts) + f'" fill="{fill}"{s}/>')

# ---- 富文本换行：每个条目 = [(文本, 是否加粗)]，带悬挂缩进编号 ----
def wrap_runs(runs, width, fs):
    chars = [(ch, b) for t, b in runs for ch in t]
    lines, cur, cw = [], [], 0.0
    for ch, b in chars:
        k = tw(ch, fs, b)
        if cw + k > width and cur:
            lines.append(cur); cur, cw = [], 0.0
        cur.append((ch, b)); cw += k
    if cur: lines.append(cur)
    out = []
    for ln in lines:  # 合并相邻同样式字符
        segs = []
        for ch, b in ln:
            if segs and segs[-1][1] == b: segs[-1][0] += ch
            else: segs.append([ch, b])
        out.append(segs)
    return out

def items_height(items, width, fs, lh, gap, numbered, indent=22):
    h = 0
    for i, it in enumerate(items):
        n = len(wrap_runs(it, width - (indent if numbered else 0), fs))
        h += n * lh + (gap if i < len(items) - 1 else 0)
    return h

def draw_items(x, y, items, width, fs, lh, gap, numbered, numcol, textcol, indent=22, bullet=False):
    cy = y
    for i, it in enumerate(items):
        ind = indent if (numbered or bullet) else 0
        lines = wrap_runs(it, width - ind, fs)
        if numbered:
            T(x, cy + lh * 0.5 + fs * 0.36, f'{i + 1}.', fs, numcol, 'bold', 'start')
        elif bullet:
            a(f'<circle cx="{x + 5:.1f}" cy="{cy + lh * 0.5:.1f}" r="3" fill="{numcol}"/>')
        for ln in lines:
            xx = x + ind
            for seg, b in ln:
                T(xx, cy + lh * 0.5 + fs * 0.36, seg, fs, "#111827" if b else textcol, 'bold' if b else 'normal', 'start')
                xx += tw(seg, fs, b)
            cy += lh
        cy += gap
    return cy - gap

def lead(s, body):
    return [(s, True), (body, False)]
def plain(s):
    return [(s, False)]

# ================= 数据（虚构示例，仅用于演示版式；实际使用时逐字取自原画板） =================
JOURNEY = ["品牌认知", "兴趣探索", "购买决策", "产品交付", "安装调试", "产品使用", "维修保养", "复购推荐"]
VALUE = ["洞察与需求分析", "规划与产品开发", "营销执行", "渠道与门店运营", "产品交付", "用户使用体验", "用户服务", "用户增值"]

BA = [
    ("1.0 产品开发", [plain("组织协同不足：跨部门开发团队职责不清，产品开发组织未显性呈现"),
                    plain("流程贯通：平台与通用模块数据未及时更新，开发阶段复用场景缺失，端到端未贯通；")], "80.0%", "5.0%"),
    ("3.4 管理渠道", [plain("方案设计、报价、合同签订依赖门店人工操作，方案标准化不足，输出效率偏低；"),
                    plain("商机到合同链路缺少过程留痕，过程信息无沉淀；"),
                    plain("门店销售动作缺少统一管控，方案与报价口径不一致，影响客户体验与成交转化；")], "40.0%", "0%"),
    ("3.5 管理零售", [plain("安装耗材仅照片反馈，缺少结构化数据，成本分析与质量追溯困难；"),
                    plain("约 20% 用户安装信息无法获取，用户信息缺失，影响后续保修确认；"),
                    plain("共享仓推广后，发货产品与合同对应关系错乱，结算功能失效；")], "55.0%", "0%"),
    ("3.7 管理服务", [plain("未结合渠道运营数据进行渠道分级运营"),
                    plain("服务稽查在线下开展，执行标准与规范未通过系统固化提效")], "60.0%", "0.5%"),
    ("4.0 用户运营", [plain("老用户积分获取、使用途径单一，推荐积极性未完全激活"),
                    plain("积分逆向流程未实现，用户权益保障不足"),
                    plain("触点集中于推荐环节，中间运营断层，老用户沉寂，召回与转化难度大，易流失")], "15.0%", "1.0%"),
]

# 状态色：待建设 / 待推广 / 待优化 / 已上线
ST = {
    "build": ("#dde2f8", "#a7b2e6"),   # 待建设
    "promo": ("#fde0df", "#eea5a2"),   # 待推广
    "opt":   ("#fdeebd", "#e6c76a"),   # 待优化
    "live":  ("#f6faff", "#a9c7f2"),   # 已上线
}
AA = [
    ("需求/产品系统", [[("需求管理", "opt"), ("项目管理", "live"), ("零部件管理", "live")],
                   [("规划管理", "live"), ("产品管理", "live"), ("BOM管理", "live")]],
     [lead("场景覆盖不全：", "已实现需求到产品路标和产品开发的分发闭环，但需求到产品改进、平台路标、技术开发的分发链路未打通。")]),
    ("客户关系系统", [[("活动管理", "live"), ("渠道管理", "live"), ("库存管理", "opt")],
                  [("商机管理", "opt"), ("销售跟进", "live"), ("流量聚合", "build")]],
     [lead("流量聚合：", "缺少对接各内容平台接口、24 小时智能客服、一键外呼、智能标签并回传客户系统的综合聚合平台"),
      lead("商机跟进：", "系统对门店导购缺少实质管理动作，商机回访没有跟进记录"),
      lead("商家库存：", "借助共享仓实现精准商家库存管理，")]),
    ("销售系统", [[("订单管理", "opt"), ("政策管理", "opt"), ("回款管理", "live")],
              [("样机管理", "live"), ("退换货管理", "live"), ("安装管理", "live")]],
     [lead("用户体验：", "经销商操作入口分散，需在多套系统间频繁切换，流程割裂、效率低下，整体体验欠佳。"),
      lead("系统架构：", "平台技术架构老化，稳定性存在隐患，扩展性受限，难以支撑业务持续发展。"),
      lead("订单透明：", "订单履约全流程透明度不足，经销商无法实时掌握订单状态，信息反馈滞后。")]),
    ("服务系统", [[("服务商管理", "live"), ("售后管理", "opt"), ("配件管理", "live")],
              [("AI智能客服", "promo"), ("结算管理", "live"), ("增值服务", "opt")]],
     [lead("链路断裂：", "一套业务分散在多个系统，数据链路断裂，业务管理与服务商机转化难度大"),
      lead("精度不足：", "电子围栏精度不足，派工效率受影响"),
      lead("AI能力：", "智能客服未引入大模型，排查信息未传递后端，现场处置依赖手工")]),
    ("用户洞察/会员", [[("用户声音洞察", "live"), ("用户画像洞察", "promo"), ("用户资产管理", "promo")],
                   [("会员管理", "build"), ("用户体验管理", "opt")]],
     [lead("用户画像洞察缺乏数据支撑。", "缺少会员画像与需求洞察工具，无会员数据支撑精准洞察。"),
      lead("会员体系与活动营销空白。", "无会员等级/积分/权益/生命周期；活动营销、拉新均无系统支撑，难以形成拉新-激活-留存-推荐闭环。"),
      lead("全旅程体验线上化不足。", "售前（展厅/门店）、售中（订单/安装/交付）未接入用户端；售后保养/满意度/保修政策待建设，数据分散在多个系统。")]),
]

DA_L = ["指标自动化水平低，跨业务链路存在数据断点，自建看板与统一门店管理口径不一致。",
        "客户主数据需要加强治理，部分维度标准、口径不统一，查重治理落地不足。",
        "用户、会员数据沉淀不足，数据责任和问题闭环机制缺失（设备数据/舆情等）。"]
DA_R = ["销售到回款的知识体系未建立，相关知识未系统入库",
        "产品知识未纳入客服服务，产品卖点等未进入智能应用范围，因此未系统化治理",
        "已入库知识使用率不高（覆盖率 66%，使用率 33%），无法保证质量"]

LEGEND = [("待建设", "build", ["已有应用不适用，", "需要新建"]), ("待推广", "promo", ["已有应用，需要推", "广到业务单元"]),
          ("待优化", "opt", ["已有应用，需要根", "据需求优化"]), ("已上线", "live", ["应用已上线运营"])]

# ================= 版式常量 =================
CW, LEFT, RIGHT = 2185, 167, 2170          # 画布内容宽 / 内容区左右边界
CARD_X, CARD_W = 0, 2185
PAD = 18
COLW, COLP = 391, 403                       # 五列：宽 / 间距
FS, LH, GAP = 15, 24, 6

INK, SUB = "#1f2937", "#475569"
ACC = {"j": ("#c98a12", "#fff8e6"), "v": ("#2f9e5b", "#eef9f1"), "ba": ("#3b6fd4", "#eef4ff"),
       "aa": ("#0e8f8d", "#e8f6f6"), "da": ("#8e44b8", "#f7effc")}

def tag(x, y, kind, prefix, name):
    col, bg = ACC[kind]
    R(x, y, 124, 46, bg, col, 10, 1.2)
    if prefix:
        wp = tw(prefix, 18, True); wn = tw(name, 18, True); sx = x + 62 - (wp + wn) / 2
        T(sx, y + 23 + 18 * 0.36, prefix, 18, col, 'bold', 'start')
        T(sx + wp, y + 23 + 18 * 0.36, name, 18, INK, 'bold', 'start')
    else:
        TC(x + 62, y + 23, name, 18, INK, 'bold')

def card(y, h):
    R(CARD_X, y, CARD_W, h, "#ffffff", "#d8e0ea", 16, 1, True)

def sublabel(y, text, kind):
    col, _ = ACC[kind]
    a(f'<rect x="20" y="{y + 3:.1f}" width="4" height="18" rx="2" fill="{col}"/>')
    T(32, y + 12 + 16 * 0.36, text, 16, INK, 'bold', 'start')

def col_x(i): return LEFT + i * COLP

# ---- 先计算各卡高度 ----
TXTW = COLW - 32
ba_text_h = max(items_height(it, TXTW, FS, LH, GAP, True) for _, it, _, _ in BA)
aa_text_h = max(items_height(it, TXTW, FS, LH, GAP, True) for _, _, it in AA)
MET_H = 69
h_top = PAD + 46 + 12 + 46 + PAD
h_ba = PAD + 46 + 18 + ba_text_h + 16 + MET_H + PAD
CONT_H = 154
h_aa = PAD + CONT_H + 20 + aa_text_h + PAD
DA_HEAD, DA_BODY = 40, 120
h_da = PAD + DA_HEAD + 8 + DA_BODY + PAD

y_top = 0
y_ba = y_top + h_top + 20
y_aa = y_ba + h_ba + 20
y_da = y_aa + h_aa + 20
y_leg = y_da + h_da + 22
H = y_leg + 44

W_ALL, H_ALL = CW + 80, H + 64
a(f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W_ALL}" height="{H_ALL:.0f}" viewBox="0 0 {W_ALL} {H_ALL:.0f}">
<defs>
<linearGradient id="gj" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff3d2"/><stop offset="1" stop-color="#fde6ae"/></linearGradient>
<linearGradient id="gv" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#e6f7ec"/><stop offset="1" stop-color="#cdeedb"/></linearGradient>
<linearGradient id="gb" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#d9e8ff"/><stop offset="1" stop-color="#bcd6fb"/></linearGradient>
<linearGradient id="gt" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e3f5f4"/><stop offset="1" stop-color="#cdebe9"/></linearGradient>
<filter id="sh" filterUnits="userSpaceOnUse" x="-60" y="-60" width="{W_ALL + 120}" height="{H_ALL + 120:.0f}"><feDropShadow dx="0" dy="2" stdDeviation="5" flood-color="#0f172a" flood-opacity="0.07"/></filter>
</defs>
<rect width="{W_ALL}" height="{H_ALL:.0f}" fill="#eef2f7"/>
<g transform="translate(40,32)">''')

# ---- 顶部：用户旅程 / 价值流 ----
card(y_top, h_top)
D = 22
span = RIGHT - LEFT
p = (span - D + 8) / 8
w = p + D - 8
for k, (row, grad, stroke, txtc, kind, name) in enumerate([(JOURNEY, "url(#gj)", "#ecc66a", "#5b3d00", "j", "用户旅程"),
                                                           (VALUE, "url(#gv)", "#8fd0a8", "#14532d", "v", "价值流")]):
    yy = PAD + k * 58
    tag(20, y_top + yy, kind, "", name)
    for i, t in enumerate(row):
        x0 = LEFT + i * p
        chev(x0, y_top + yy, w, 46, D, grad, stroke, flat=(i == 0))
        TC(x0 + ((D if i else 0) + w - D) / 2, y_top + yy + 23, t, 15, txtc)

# ---- BA ----
card(y_ba, h_ba)
tag(20, y_ba + PAD, "ba", "BA", "流程架构")
sublabel(y_ba + PAD + 46 + 18, "业务差距", "ba")
CH = 20
for i, (title, items, on, sm) in enumerate(BA):
    x0 = col_x(i)
    wch = COLW + (COLP - COLW) + CH - 8 if i < 4 else COLW
    chev(x0, y_ba + PAD, wch, 46, CH, "url(#gb)", "#86aef0", flat=(i == 0))
    TC(x0 + ((CH if i else 0) + wch - CH) / 2, y_ba + PAD + 23, title, 16, "#17306b", 'bold')
    ty = y_ba + PAD + 46 + 18
    draw_items(x0 + 8, ty, items, TXTW, FS, LH, GAP, True, "#3b6fd4", SUB)
    my = y_ba + h_ba - PAD - MET_H
    mx = x0 + (COLW - 232) / 2
    for j, (lab, val, bg, bd, lc, vc) in enumerate([("线上化率", on, "#eaf8ef", "#bfe6cc", "#3f8f5e", "#15803d"),
                                                     ("智能化率", sm, "#fdf0e6", "#f3d3b3", "#b9763a", "#c2492f")]):
        bx = mx + j * 122
        R(bx, my, 110, MET_H, bg, bd, 12, 1)
        TC(bx + 55, my + 17, lab, 12.5, lc, 'normal')
        TC(bx + 55, my + 44, val, 25, vc, 'bold')

# ---- AA ----
card(y_aa, h_aa)
tag(20, y_aa + PAD, "aa", "AA", "应用架构")
sublabel(y_aa + PAD + CONT_H + 20, "应用差距", "aa")
CELL_W, CELL_H = 114, 42
for i, (title, rows, items) in enumerate(AA):
    x0 = col_x(i); y0 = y_aa + PAD
    R(x0, y0, COLW, CONT_H, "url(#gt)", "#9fd3d1", 14, 1)
    TC(x0 + COLW / 2, y0 + 23, title, 18, "#0b5f5e", 'bold')
    for r, row in enumerate(rows):
        for c, (nm, st) in enumerate(row):
            fill, bd = ST[st]
            bx = x0 + 14 + c * (CELL_W + 10); by = y0 + 46 + r * 54
            R(bx, by, CELL_W, CELL_H, fill, bd, 9, 1)
            TC(bx + CELL_W / 2, by + CELL_H / 2, nm, 14.5, INK)
    draw_items(x0 + 8, y0 + CONT_H + 20, items, TXTW, FS, LH, GAP, True, "#0e8f8d", SUB)

# ---- DA ----
card(y_da, h_da)
tag(20, y_da + PAD, "da", "DA", "数据架构")
sublabel(y_da + PAD + DA_HEAD + 8 + DA_BODY / 2 - 12, "共性问题", "da")
PW = 986
for k, (title, items) in enumerate([("数据治理", DA_L), ("知识管理", DA_R)]):
    px = LEFT + k * (PW + 13); py = y_da + PAD
    R(px, py, PW, DA_HEAD, "#f0e3f8", "#d9bfeb", 10, 1)
    TC(px + PW / 2, py + DA_HEAD / 2, title, 18, "#5e2384", 'bold')
    by = py + DA_HEAD + 8
    R(px, by, PW, DA_BODY, "#fdf9ff", "#ecdcf5", 12, 1)
    its = [plain(s) for s in items]
    hh = items_height(its, PW - 60, FS, 26, 4, False) if False else len(items) * 26 + 2 * 4
    draw_items(px + 28, by + (DA_BODY - hh) / 2, its, PW - 60, FS, 26, 4, False, "#8e44b8", SUB, indent=20, bullet=True)

# ---- 图例 ----
gx = CW - 990
for nm, st, desc in LEGEND:
    fill, bd = ST[st]
    R(gx, y_leg, 87, 40, fill, bd, 9, 1)
    TC(gx + 43.5, y_leg + 20, nm, 14.5, INK)
    a(f'<rect x="{gx + 99}" y="{y_leg + 3}" width="2" height="34" rx="1" fill="#cbd5e1"/>')
    for li, ln in enumerate(desc):
        T(gx + 110, y_leg + (20 if len(desc) == 1 else 15 + li * 17) + 12.5 * 0.36, ln, 12.5, "#64748b", 'normal', 'start')
    gx += 87 + 22 + 134 + 8 + 2
a('</g></svg>')
open('diagram.svg', 'w').write('\n'.join(o))
print(round(W_ALL), round(H_ALL), 'ba_h', ba_text_h, 'aa_h', aa_text_h)
