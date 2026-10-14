# 飞书画板适配器：执行流程

## 0. 准备
- 依赖：`lark-cli`（已登录，`--as user`）、`npx`（拉取 `@larksuite/whiteboard-cli@^0.2.13`）、`python3`；
  可选 Pillow（文字宽度实测、生成模型查看图与长图切片）；macOS 无 Pillow 时 review 缩图回退 `sips`，但切片仍需 Pillow。
- **图片双轨**：`preview.jpg` / `diagram.png` 保留完整分辨率供交付；自动生成的 `preview.review.jpg` / `diagram.review.png`
  最长边为 1920px，专供模型查看。不要把完整图与其他图片一起发送给模型。
- 运行目录根：默认 `./_runs`，可用环境变量 `WB_RUNS_ROOT` 或 `--runs-root` 指定。产物写在用户工作目录，**不写进 skill 目录**。
- 字体：`core/text.py` 自动查找 `~/.npm/_npx/*/node_modules/@larksuite/whiteboard-cli/dist/fonts`；找不到时先跑一次 `check.sh`
  让 npx 下载，或设 `WB_FONT_DIR`。

## 1. 导出（只读）
`python3 scripts/adapters/feishu/export.py "<链接或token>" --slug <短名> [--reference "<参考链接或token>"]`
- 支持带 `blockToken=` 的文档/wiki 链接、`/board/<token>`、裸 token。wiki/文档链接若没有 `blockToken`，
  让用户在飞书里点开画板后复制链接，或用 `lark-cli docs +fetch` 找画板块 token。
- 输出打印节点类型统计；完整原图在 `source/preview.jpg`，模型只读取自动生成的 `source/preview.review.jpg`。

## 2. 生成
`python3 scripts/adapters/feishu/redraw.py source/raw.json -o diagram.svg --report report.json [--mode standard] [--font 微软雅黑]`
- 档位见 SKILL.md：`conservative` 只改配色；`standard`（默认）加排版规整；`aggressive` 再按需撑高行。
  报告里的 `layout`（每组移动了几个、最大位移、统一后的行列间距）、`font_tiers`（字号分档）要看一眼。
- 标准档起，换行按 whiteboard-cli 检查器的实测口径计算：普通文字约每字 1em，粗体约 1.17em（取 1.18 留余量），可避免 text-overflow 误报。
- 引擎做的事：按角色（容器/卡片/流程箭头/表格/文本/连线/图标/遮罩）重绘；原色按色相归入 7 个色系（中性/青/蓝/绿/琥珀/红/紫）
  的浅底或深底，同一原色始终映射到同一新色；半透明填充按叠在白底后的观感色归类。富文本保留硬换行、粗体和列表符号，超宽时均衡换行；standard 最多缩字 10%，仍放不下则撑高整行。
- 字号很大的画板（中位字号 > 24，如 36px 文字）会整体等比缩放到约 16px，`report.json` 的 `scale` 记录比例。
- 先看终端里的 `warnings`，再看 `report.json` 的 `color_map`（原色 → 色系），确认归类合理。

## 3. 检查
`bash scripts/adapters/feishu/check.sh diagram.svg --png` → 必须 `errors=0 warnings=0`；
`python3 scripts/adapters/feishu/verify_text.py source/raw.json diagram.svg` → 必须 `missing=0 extra=0`。
`--png` 同时保留完整 `diagram.png` 并生成最长边 1920px 的 `diagram.review.png`；模型只读取 review 图。
长画板缩小后看不清时，按需生成局部切片：
```bash
python3 scripts/core/review_image.py diagram.png -o diagram.review.png --tiles-dir review-tiles
```
每张切片的宽、高都小于 2000px；**一次只看一张，分轮查看**，不要把全部切片放进同一请求。

## 4. 调整（按代价从低到高）
1. **颜色归类不对**：`--map "#原色=色系/soft|solid|white"`，可多次。例：原图浅灰底其实表示「已完成」，`--map "#bbbfc4=neutral/soft"`。
2. **整套配色要换**：写 `style.json` 覆盖 `scripts/core/palette.json` 的任意字段，`--style style.json`。
3. **个别角色要特殊处理**（如某类标签做成竖条标签卡、价值目标横幅）：在运行目录写 `gen.py`，
   `from redraw import Painter` 后子类化覆盖对应 `draw_*` 方法，主引擎不改。历史手写案例见开发仓库 `_runs/diagrams/`。
4. **排版规整仍不理想**：先换 `--mode aggressive`；若需要改变元素数量、包含关系或阅读顺序才可解决，停下来问用户。

改引擎本身（`adapters/feishu/redraw.py`、`lib.py` 或 `scripts/core/`）属于 skill 迭代，须跑回归（见开发仓库 `CONTRIBUTING.md`）。

## 5. 发布
`python3 scripts/adapters/feishu/publish.py <run> --title "<原标题>（配色排版优化版）" [--allow "："] [--parent-token <文件夹/wiki 节点>]`
- 先复跑本地检查，不通过不写入；新建文档 + 空白画板 → `+update --overwrite`（幂等 token 带时间戳）→ 导出线上 raw 复核。
- 线上会把多行文本拆成多段，`online_text_check` 偶尔出现差异，按字符抽查即可，不算失败。
- 成功后写回 `run.json`，并在 `<runs>/registry.json` 登记「优化画板 token → 运行目录」，供以后作参考。

## 省上下文
- 大文件（raw.json、svg、gen.py）用 grep / 行范围读；不要整文件打印 raw。
- 图片只在关键节点各看一次：`preview.review.jpg`、`diagram.review.png`。完整原图不传给模型；局部切片逐张分轮查看。
- 本 skill 的 references 只读当前步骤需要的一篇。
- 多个无关画板任务尽量分开会话；同会话连续处理时，每块画板一个运行目录。
