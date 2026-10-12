# PPT 适配器（.pptx）

**写回方式：原位改色。** 不重绘页面，只改幻灯片 XML 里显式颜色（`<a:srgbClr>`）的值，以及母版主题的 accent1–6 定义。
因此母版、版式、动画、备注、超链接、图片、图表、SmartArt、每个形状的位置尺寸和文字都原样保留。

## 0. 准备
- 只支持 `.pptx`。`.ppt` / `.key` 请用户先另存为 `.pptx`。
- 依赖：`python-pptx==1.0.2`（含 lxml）；渲染检查另需 `pypdfium2==4.30.0`、Pillow，以及本机 Microsoft PowerPoint（macOS）。
  没有 PowerPoint 时跳过渲染（`--no-render`），在交付时说明「未目检」。
- 运行目录根同飞书：默认 `./_runs`。

## 1. 一条命令跑完（推荐）
```bash
python3 <skill>/scripts/restyle.py "<文件>.pptx" --slug <短名> [--brand "#00aaa6"|none]
```
产出 `<run>/<原名>（优化版）.pptx`、`plan.json`、`render/compare-NN.png`（上原图、下优化版，每页一张）。

## 2. 分步（需要调整方案时）
```bash
P=<skill>/scripts/adapters/pptx
python3 $P/plan.py   in.pptx -o plan.json [--brand ...] [--map "#ffb940=amber/accent"] [--style style.json]
python3 $P/apply.py  in.pptx plan.json -o "XX（优化版）.pptx"
python3 $P/verify.py in.pptx "XX（优化版）.pptx"            # 必须输出 ok
python3 $P/render.py "XX（优化版）.pptx" -o render --compare in.pptx
```
`plan.json` 是样式方案：`map`（原色 → 新色，含次数和页码）、`kept`（不改的颜色及原因）、`converged`（多个原色收敛为同一新色）、
`brand`、`warnings`（对比度不足等）。可以手改 `map` 里的 `to` 再跑 `apply.py`。

## 3. 改色规则（plan.py）
| 位置 | 规则 |
|---|---|
| 形状 / 表格填充 | 彩色按观感色（透明度与白底混合后）分深浅：很浅 → soft 底；很深 → solid；其余 → accent。浅色半透明底换成等效不透明浅底 |
| 线条 | 彩色 → 同色系 accent（很浅的 → soft 描边） |
| 文字 | 彩色字 → 所在色系文字色（如各种红统一为 `#b3292c`）；彩色底上的彩色字 → 底色配套文字色 |
| 主题 accent1–6 | 仅改幻灯片实际引用的槽位；两个槽位不能收敛成同一色（图表系列靠它区分），撞色时后者不改 |
| 中性色（黑白灰） | 不改（正文多继承母版黑色，只改显式黑色会深浅不一） |
| 阴影 / 发光等效果色、schemeClr 引用、图片、图表内部 | 不改 |
- 品牌色：默认取母版里最常用的彩色；`--brand none` 关闭，`--brand "#hex"` 指定。品牌色本身不改，同色系近似色收敛到它。
- 字号与字体：本版不改（避免溢出）；需要统一字体时问用户要哪套字体。

## 4. 检查（完成标准）
1. `verify.py` 输出 `ok`：部件清单一致；幻灯片与主题以外的部件逐字节相同；每页 XML 抹掉颜色值后完全相同；逐页文字一致。
2. `plan.json` 的 `warnings` 为空，或已向用户说明。
3. 看一次 `render/compare-NN.png`（每页一张，只看一次）。

## 5. 交付时告诉用户
优化版文件路径；颜色收敛情况（`converged`：哪些原色合并成了哪个新色）；品牌色；没有改的部分（中性色、图片、图表、字号）；
校验结果；未验证项（如没有 PowerPoint 时未目检、Windows 上字体渲染差异）。
