# Changelog

面向 skill 使用者，只记能力变化。维护过程见 `PROJECT_CONTEXT.md`。

## [0.2.0] - 2026-10-13
定位从「飞书画板」扩展为「自由画布类内容」，skill 改名 `canvas-restyle`（原 `feishu-whiteboard-restyle`）。
### Added
- PPT 适配器（`.pptx`）：整份文件生成样式方案 `plan.json` → 在副本上原位改色 → `verify.py` 证明只改了颜色 → PowerPoint 渲染对比图。
  保留母版、动画、备注、图片、图表与所有位置尺寸；品牌色（母版最常用彩色）不改，同色系近似色收敛到它；
  主题 accent1–6 只改被引用的槽位且不让两个槽位撞色；中性色不改。
- 统一入口 `scripts/restyle.py`：按输入类型（.pptx / 飞书链接）分发到适配器。
- 色板新增 `accent` 深浅（中等饱和强调色）与品牌色锚定。
- `references/principles.md`：与工具无关的通用视觉原则。
### Changed
- 目录改为核心层 + 适配器：`scripts/core/`（色系归类、色板、文字颜色、文字测量、几何）、`scripts/adapters/feishu/`、`scripts/adapters/pptx/`；
  飞书相关文档移到 `references/adapters/`。飞书画板的输出与 0.1.0 逐字节一致。
- 两个数据驱动模板的数据段改为虚构示例，`reference.svg/png` 随之重新生成（版式与配色不变）。
- 模板注册表 `registry.json` 不再内置基准画板 token / 链接，改由同目录本地文件 `registry.local.json`（结构相同）提供，两者合并查找。

## [0.1.0] - 2026-10-12
首个 skill 版本，由此前 15 次画板优化的经验整合而成。

### Added
- 默认引擎 `redraw.py`：读飞书画板 raw 原位重绘，适用于任意画板。识别容器、卡片、流程箭头、表格、文本、连线、图标、半透明遮罩；
  原色按色相归入 7 个色系，同一原色映射到同一新色；保留硬换行、均衡换行、放不下时自动缩字号；大字号画板整体等比缩放。
- 自动规避 whiteboard-cli 检查器误报：容器/条纹/表格底与需叠放的卡片画成多边形；细条装饰画成粗线；小图标避让文字。
- 参考模式：用户明确指定参考画板时，命中模板注册表走数据驱动模板（运营看板、BA/AA/DA 架构图），否则用 `extract_style.py` 迁移配色。
- 脚本：`export.py`（解析链接、导出、建运行目录）、`check.sh`（0/0 检查与渲染）、`verify_text.py`（字符多重集比对）、
  `publish.py`（本地复检 → 新建文档写入 → 线上复核 → 登记运行注册表，拒绝写入原画板）。
- 文档：执行流程、角色规则、SVG 约束、默认色板、参考模式，以及运营看板、BA/AA/DA、分层架构三篇风格经验。
