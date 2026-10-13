---
name: canvas-restyle
version: 0.2.1
description: >
  自由画布类内容的样式优化：飞书画板、PPT（.pptx）等，在不改内容、文字、元素位置与结构的前提下，
  统一配色、收敛近似色、理顺文字颜色层级，产出新文件 / 新画板（原件只读）。当用户要求「优化/美化这个画板或 PPT 的配色、
  样式、排版」「统一这份 PPT 的颜色」「参考某画板的风格优化这个画板」时使用。所有工具共用同一套视觉原则，
  按工具特性分别落地。不负责：改内容或结构、从零制作、重新设计版式（重做 PPT 用 slide-maker，飞书画板绘制用 lark-whiteboard）。
metadata:
  requires:
    bins: ["python3"]
    optional: ["lark-cli（飞书）", "npx（飞书检查器）", "Microsoft PowerPoint（仅用于自动渲染 PPT 预览图，没有就跳过；WPS 用户不必安装）"]
---

# 画布样式优化（canvas-restyle）

## 铁律（所有工具）
1. **原件只读**。飞书写入新建文档里的新画板；PPT 输出 `<原名>（优化版）.pptx`。脚本会拒绝覆盖原件。
2. **内容不变**：文字逐字保留，元素数量、位置、尺寸、层级不变；只改样式。
3. **同一套视觉原则**：见 `references/principles.md`。颜色决策统一来自 `scripts/core/`（色系归类、色板、品牌色锚定、文字颜色规则）。
4. **不猜语义**：没有图例时不新增图例、不臆测颜色含义，只保留「同色同类、异色异类」。
5. **完成标准按工具**（见下表），缺一不可；没验证的项在交付时说明。

## 按输入路由
| 输入 | 适配器 | 写回方式 | 完成标准 | 详细流程 |
|---|---|---|---|---|
| 飞书画板 / 带 blockToken 的文档链接 / token | 飞书 | raw 原位重绘为 SVG，写入新画板（飞书只能 SVG 导入） | check 0/0 → 文字一致 → 写入新画板 → 线上 raw 复核 | `references/adapters/feishu.md` |
| `.pptx`（PowerPoint 或 WPS 生成均可） | PPT | 在副本上原位改色（不重绘，保留母版、动画、图表） | `verify.py` ok（只改了颜色）→ 方案无警告 → 有对比图则看一次 | `references/adapters/pptx.md` |
| `.ppt` / `.key` | — | 请用户先另存为 `.pptx` | | |
| draw.io、飞书幻灯片 | 未实现 | 告诉用户暂不支持 | | |

统一入口（读取 → 样式方案 → 落地 → 校验，不发布）：
```bash
python3 <skill>/scripts/restyle.py "<文件.pptx | 飞书画板链接>" --slug <短名>
```
飞书画板确认效果后再跑 `scripts/adapters/feishu/publish.py`（写入无需逐次确认，用户已授权；只写新建画板）。

## 飞书：引擎选择
| 情况 | 引擎 |
|---|---|
| **默认**（用户没有明确指定参考画板） | raw 原位重绘 `adapters/feishu/redraw.py` |
| 用户**明确**说「以 X 为参考/模板」并给出画板，且 X 的 token 在 `templates/registry.json` / `registry.local.json` | 数据驱动模板：复制 `templates/<name>/gen.py`，只换数据段 |
| 同上，X 不在注册表 | 样式迁移：`adapters/feishu/extract_style.py` → `redraw.py --style` |
「参考刚才的风格」这类没给具体画板的说法不算指定参考。细节见 `references/adapters/feishu-reference-mode.md`（只在命中时读）。

## 要先问用户的情况
- 要好看只能靠移动 / 缩放元素（违反布局不变）。
- 飞书：重绘报告里有「原图卡片部分重叠」「独立文本压在形状上」且影响阅读；参考模式下结构与模板不一致；链接解析不出 token。
- PPT：方案里有对比度警告；用户想统一字体或字号（本版默认不改）；颜色明显承载语义但归类存疑。

## 交付时告诉用户
产出位置（新文档链接 / 优化版文件路径）；做了哪些调整（颜色收敛：哪些原色合并成哪个新色；品牌色）；
任何偏离原图之处（飞书：流程箭头去叠压、遮罩改虚线框）；校验结果；未验证项。

## 文件索引（按需读取，不要一次全读）
| 文件 | 何时读 |
|---|---|
| `references/principles.md` | 每次执行 |
| `references/adapters/feishu.md` | 飞书画板；含调整手段、省上下文规则 |
| `references/adapters/feishu-roles.md` | 飞书引擎识别角色出错、需要 `--map` 或覆盖脚本时 |
| `references/adapters/feishu-svg-constraints.md` | 飞书 `check.sh` 报错 / 手写 SVG 时 |
| `references/adapters/feishu-reference-mode.md`、`references/styles/*.md` | 飞书参考模式 |
| `references/adapters/pptx.md` | PPT |
| `references/palette.md` | 调整色板、品牌色时 |
