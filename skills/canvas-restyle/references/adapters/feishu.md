# 飞书画板适配器：执行流程

## 0. 准备
- 依赖：`lark-cli`（已登录，`--as user`）、`npx`（拉取 `@larksuite/whiteboard-cli@^0.2.13`）、`python3`；
  可选 Pillow（文字宽度实测，未安装则用估算系数，换行略保守）。
- 运行目录根：默认 `./_runs`，可用环境变量 `WB_RUNS_ROOT` 或 `--runs-root` 指定。产物写在用户工作目录，**不写进 skill 目录**。
- 字体：`core/text.py` 自动查找 `~/.npm/_npx/*/node_modules/@larksuite/whiteboard-cli/dist/fonts`；找不到时先跑一次 `check.sh`
  让 npx 下载，或设 `WB_FONT_DIR`。

## 1. 导出（只读）
`python3 scripts/adapters/feishu/export.py "<链接或token>" --slug <短名> [--reference "<参考链接或token>"]`
- 支持带 `blockToken=` 的文档/wiki 链接、`/board/<token>`、裸 token。wiki/文档链接若没有 `blockToken`，
  让用户在飞书里点开画板后复制链接，或用 `lark-cli docs +fetch` 找画板块 token。
- 输出打印节点类型统计；看一次 `source/preview.jpg` 了解画面。

## 2. 生成
`python3 scripts/adapters/feishu/redraw.py source/raw.json -o diagram.svg --report report.json`
- 引擎做的事：按角色（容器/卡片/流程箭头/表格/文本/连线/图标/遮罩）重绘；原色按色相归入 7 个色系（中性/青/蓝/绿/琥珀/红/紫）
  的浅底或深底，同一原色始终映射到同一新色；保留原硬换行，超宽时均衡换行，放不下时逐步缩字号（下限原字号 70%）。
- 字号很大的画板（中位字号 > 24，如 36px 文字）会整体等比缩放到约 16px，`report.json` 的 `scale` 记录比例。
- 先看终端里的 `warnings`，再看 `report.json` 的 `color_map`（原色 → 色系），确认归类合理。

## 3. 检查
`bash scripts/adapters/feishu/check.sh diagram.svg --png` → 必须 `errors=0 warnings=0`；
`python3 scripts/adapters/feishu/verify_text.py source/raw.json diagram.svg` → 必须 `missing=0 extra=0`。
看一次 `diagram.png`（关键节点只看一次；长图可用 PIL 裁局部看）。

## 4. 调整（按代价从低到高）
1. **颜色归类不对**：`--map "#原色=色系/soft|solid|white"`，可多次。例：原图浅灰底其实表示「已完成」，`--map "#bbbfc4=neutral/soft"`。
2. **整套配色要换**：写 `style.json` 覆盖 `scripts/core/palette.json` 的任意字段，`--style style.json`。
3. **个别角色要特殊处理**（如某类标签做成竖条标签卡、价值目标横幅）：在运行目录写 `gen.py`，
   `from redraw import Painter` 后子类化覆盖对应 `draw_*` 方法，主引擎不改。历史手写案例见开发仓库 `_runs/diagrams/`。
4. **需要移动/缩放节点才能好看**：停下来问用户（违反「布局不变」）。

改引擎本身（`adapters/feishu/redraw.py`、`lib.py` 或 `scripts/core/`）属于 skill 迭代，须跑回归（见开发仓库 `CONTRIBUTING.md`）。

## 5. 发布
`python3 scripts/adapters/feishu/publish.py <run> --title "<原标题>（配色排版优化版）" [--allow "："] [--parent-token <文件夹/wiki 节点>]`
- 先复跑本地检查，不通过不写入；新建文档 + 空白画板 → `+update --overwrite`（幂等 token 带时间戳）→ 导出线上 raw 复核。
- 线上会把多行文本拆成多段，`online_text_check` 偶尔出现差异，按字符抽查即可，不算失败。
- 成功后写回 `run.json`，并在 `<runs>/registry.json` 登记「优化画板 token → 运行目录」，供以后作参考。

## 省上下文
- 大文件（raw.json、svg、gen.py）用 grep / 行范围读；不要整文件打印 raw。
- 图片只在关键节点各看一次：原图 preview、最终 diagram.png。
- 本 skill 的 references 只读当前步骤需要的一篇。
- 多个无关画板任务尽量分开会话；同会话连续处理时，每块画板一个运行目录。
