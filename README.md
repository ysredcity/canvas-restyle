# canvas-restyle

自由画布类内容样式优化 skill 的开发仓库：飞书画板、PPT（.pptx）等，在不改内容、文字、元素位置与结构的前提下，
统一配色、收敛近似色、理顺文字颜色层级，产出新文件 / 新画板（原件只读）。

- **skill 本体**：[`skills/canvas-restyle/`](skills/canvas-restyle/SKILL.md)（目前只开发，未安装）
- **架构**：核心层（`scripts/core/`，与工具无关的样式决策）+ 适配器（`scripts/adapters/<工具>/`，各自的读取与写回）
- **已支持**：飞书画板（raw 重绘为 SVG 写入新画板）、PPT（副本原位改色）；draw.io、飞书幻灯片列为后续适配器

## 目录
```
skills/canvas-restyle/              skill 本体（随 skill 分发的只有这里）
  SKILL.md                          铁律、按输入路由、完成标准
  references/principles.md          通用视觉原则
  references/adapters/              各工具的流程与约束（feishu*.md、pptx.md）
  references/palette.md · styles/   色板说明；飞书模板风格经验
  scripts/restyle.py                统一入口（按输入类型分发）
  scripts/core/                     色系归类、色板、品牌色锚定、文字颜色、文字测量、几何
  scripts/adapters/feishu/          export / redraw / check / verify_text / publish / extract_style
  scripts/adapters/pptx/            plan / apply / verify / render
  templates/                        飞书数据驱动模板（ops-board、arch-ba-aa-da）+ 注册表
tests/                              回归脚本与用例清单
docs/                               设计记录（旧 steering 存档含内部链接，仅本地保留，不入库）
_runs/                              历次执行产物、运行注册表、回归用 fixtures（不入库）
PROJECT_CONTEXT.md                  跨会话上下文台账（单一事实源）
```

## 快速试用（开发仓库内）
```bash
python3 skills/canvas-restyle/scripts/restyle.py "<文件.pptx>" --slug demo        # PPT：产出（优化版）.pptx + 对比图
python3 skills/canvas-restyle/scripts/restyle.py "<飞书画板链接>" --slug demo      # 飞书：产出 diagram.svg（发布另跑 publish.py）
```
依赖：`python3`；飞书另需 `lark-cli`（已登录）、`npx`；PPT 另需 `python-pptx==1.0.2`，渲染检查需 `pypdfium2==4.30.0`、
Pillow 与 Microsoft PowerPoint（macOS）。

## 治理
- 改动规则与回归要求：[`CONTRIBUTING.md`](CONTRIBUTING.md)
- 变更记录：[`CHANGELOG.md`](CHANGELOG.md)
- AI 协作指引：[`AGENTS.md`](AGENTS.md)
