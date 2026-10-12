# 飞书画板适配器：参考模式（仅在用户明确指定参考画板时）

## 触发判定
同时满足才进入参考模式：
1. 用户说法明确，如「以 X 为参考 / 模板」「按 X 的风格 / 版式」「和 X 一样」；
2. 给出了 X 的画板链接或 token（文档链接也可，需能解析到画板）。

只说「参考刚才的风格」「和上一个一样」而没给画板 → **不是**参考模式：走默认引擎，可复用同会话上次的 `--style` 文件。

## 步骤
1. `export.py <新画板> --slug x --reference <参考>`，得到 `reference/raw.json` 与 `run.json.reference_token`。
2. 查 `templates/registry.json` 与本地 `templates/registry.local.json`（若存在，不入库，存放真实基准画板 token）合并后的 `templates.*.tokens`：
   - **命中模板** → 数据驱动（下节）。
   - **未命中** → 查运行注册表 `<runs>/registry.json`：若参考是以前优化过的画板，记下它的 `run_dir`，
     读该目录的 `gen.py` / `style.json`（若有）作为样式来源；否则直接样式迁移。
3. 样式迁移：`adapters/feishu/extract_style.py reference/raw.json -o style.json` → `redraw.py ... --style style.json`。
   只迁移颜色；版式不迁移（版式变了就违反「布局不变」，需要用户另行确认）。

## 数据驱动模板
1. 读对应 `references/styles/<模板>.md`（仅此一篇）。
2. 比对结构：新画板的行/列/分组/步骤数是否与模板（或其文中列出的变体）一致。
   不一致 → **停下来问用户**：按最接近的变体扩展，还是退回默认引擎 + 样式迁移。
3. 复制 `templates/<模板>/gen.py` 到运行目录，**只改数据段**（`data_keys`），版式常量与配色不动。
   文字逐字取自 `source/raw.json`；原图硬换行拆成多行。
4. `python3 gen.py` → `diagram.svg`，之后同默认流程的检查与发布；`publish.py --engine template:<模板>`。
   风格文档允许的文字改动用 `--allow` 声明（如 `--allow "："`）。

## 模板回归
模板自带 `reference.svg`：在空目录复制 `gen.py` 运行，输出必须与 `reference.svg` 逐字节一致，才算模板未被改坏。
