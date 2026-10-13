# 项目上下文台账（PROJECT_CONTEXT）

> 跨会话单一事实源。最后更新：2026-10-13。

## 1. 项目是什么
开发 skill `canvas-restyle`：对自由画布类内容（飞书画板、PPT，后续 draw.io / 飞书幻灯片）做样式优化——
内容、文字、元素位置与结构不变，只统一配色与文字颜色层级，产出新画板 / 新文件。所有工具共用 `scripts/core/` 的视觉决策，
各工具由适配器落地。仓库目录 `canvas-restyle`（2026-10-13 由 feishu-whiteboard-restyle 改名，更早叫「画板优化」）。
skill 目前只开发、**未安装**。

## 2. 当前状态
- ✅ skill 0.2.0：核心层 + 适配器结构。`scripts/core/`（color / palette / text / geom + palette.json）、
  `scripts/adapters/feishu/`（原 0.1.0 全部脚本）、`scripts/adapters/pptx/`（plan / apply / verify / render）、统一入口 `scripts/restyle.py`。
- ✅ 重构零回归：飞书 7 例 SVG 与 report 与 0.1.0 **逐字节一致**（基线 `_runs/baseline-0.1.0/`），两模板与 reference.svg 一致。
- ✅ PPT 适配器在 `_runs/fixtures/pptx/测试案例.pptx`（2 页，真实业务样本）跑通：105 处改色，verify ok，
  对比图目检过第 1 页（`_runs/2026-10-12T2230-pptx-test/`）。负面测试：篡改位置 / 文字 / 图片均被 verify 拦下。
- ✅ `tests/regress.sh` 增加 PPT 段（`tests/cases-pptx.txt`），10 项全部 PASS。
- ⏳ 未做：飞书 `publish.py` 未真实写入过；skill 触发测试；未安装；PPT 只有 1 份样本，未测含表格 / 图表 / 渐变 / 多母版的 PPT。

## 3. 关键结论（不要重复踩坑）
- **远端是公开仓库** github.com/ysredcity/canvas-restyle（用户 2026-10-13 选择「保持公开、先脱敏」）：
  不入库 `docs/legacy-steering/`、`templates/registry.local.json`（真实基准画板 token / 链接）、`_runs/`；
  两个模板数据段换成虚构示例并重新生成 reference；风格文档去掉内部链接、token 与业务来源名。
  真实模板与风格文档原件备份在 `_runs/private-templates/`。以后新增内容入库前先 grep 内部域名 / token / 业务名。
- **飞书引擎选择**：默认一律 raw 重绘；只有用户明确说「以 X 为参考/模板」并给出画板时才走数据驱动或样式迁移。
- **飞书检查器规则（实测 0.2.13）**：node-overlap 只看填充 rect/path；text-overflow 把文字左上角所在形状当容器。引擎用多边形和粗线规避。
- 半透明遮罩改虚线框 + 骑线角标；流程箭头宽度收到下一个起点前（交付时说明）。
- 发布直接写入，无需逐次确认（用户 2026-10-12 授权）；但只写新建画板。
- **PPT 写回 = 原位改色**（用户 2026-10-13 同意推荐）：只改幻灯片 XML 的 srgbClr 值 / 透明度和母版主题 accent1–6，其余部件逐字节复制；
  不用 python-pptx 保存（避免重序列化副作用），zip + lxml 直接写。verify 的核心是「抹掉颜色值后 XML 完全相同」。
- **PPT 中性色不改**：正文多继承母版黑色，只改显式 #000000 会让同段文字深浅不一。
- **品牌色锚定**：母版最常用彩色视为品牌色（样本里是 #00aaa6），不改，同色系近似色（#18b4b8）收敛到它。
- **主题 accent 不能收敛撞色**：第一版把 accent1/5、accent2/4 收成同色，会让图表系列无法区分；改为只改被引用槽位、撞色时后者不改。
- PPT 饱和色不能套飞书的 soft/solid（会变成淡底或深褐），所以色板加了 `accent` 深浅；飞书引擎不使用它。
- **渲染**：PowerPoint 沙盒只能写自己的容器目录 `~/Library/Containers/com.microsoft.Powerpoint/Data/Documents`，
  且「另存为 PNG」静默失败；可行路径是导出 PDF 到容器目录 → pypdfium2 转 PNG。Keynote 脚本报 -609 不可用；本机 swift 工具链损坏。
- **渲染可选**（用户 2026-10-13 指出装了 WPS 却被引导装 PowerPoint）：PowerPoint 只用于自动预览；缺 PowerPoint / pypdfium2 / Pillow、
  导出失败或 120 秒无响应时 `render.py` 跳过并提示用 WPS 打开，退出码 0。WPS Mac 12.1 无 AppleScript，不能自动渲染。WPS 生成的 .pptx 已支持。
- Python `zipfile.writestr(info, data)` 会就地改 ZipInfo 的 CRC，复用原 ZipInfo 写新包会让原包后续读取报 CRC 错——apply.py 已改为新建 ZipInfo。
- bash 里变量名紧贴全角字符（`$name（`）会被当成变量名一部分，要写 `${name}`。

## 4. 文件地图
```
skills/canvas-restyle/
  SKILL.md                         铁律、路由、完成标准
  references/principles.md         通用视觉原则
  references/adapters/             feishu.md / feishu-roles.md / feishu-svg-constraints.md / feishu-reference-mode.md / pptx.md
  references/palette.md, styles/   色板说明；飞书模板风格
  scripts/restyle.py               统一入口
  scripts/core/                    color / palette / text / geom / palette.json
  scripts/adapters/feishu/         export / redraw / check / verify_text / publish / extract_style / lib / wb
  scripts/adapters/pptx/           pptx_lib / plan / apply / verify / render
  templates/                       飞书数据驱动模板 + registry.json
tests/regress.sh, cases.txt, cases-pptx.txt
docs/legacy-steering/              旧 4 个 steering 存档（含内部链接，仅本地，不入库）
templates/registry.local.json      真实基准画板 token（仅本地，不入库）
_runs/                             历史产物 + registry.json + fixtures/pptx/ + baseline-0.1.0/ + private-templates/，不入库
.kiro/steering/context-management.md
```

## 5. 待办
- [ ] 用一块新飞书画板跑一次 `publish.py`，验证新建文档、写入、线上复核与注册表登记。
- [ ] 更多 PPT 样本：含表格、图表、渐变、多母版、深色背景的 PPT（深色底时中性色与对比度规则需复核）。
- [ ] PPT 字号层级 / 统一字体：本版未做，需用户指定字体后再做，且要防溢出。
- [ ] 后续适配器：draw.io（改 style 字符串）、**飞书幻灯片 lark-slides**（用户 2026-10-13 要求列入）。
- [ ] 飞书引擎「装饰性增强」（层标签竖条卡、旅程渐变箭头、价值目标横幅）是否做成可选开关。
- [ ] skill 触发测试（skill-creator 的 eval）；曲线连接线目前按直线重画；安装（暂不需要）。

## 变更日志
- 2026-10-12 目录改名 feishu-whiteboard-restyle；产物移入 `_runs/`；建 skill 0.1.0（通用重绘引擎 + 参考模式 + 脚本 + 文档）与治理框架；7 例回归全部通过。
- 2026-10-13 定位扩展为自由画布，改名 canvas-restyle 0.2.0；拆出核心层 + 飞书适配器（输出逐字节不变）；新增 PPT 适配器与统一入口；
  测试 PPT 从 docs/ 移到 `_runs/fixtures/pptx/`（真实业务内容不入库）；回归 10/10。
- 2026-10-13 0.2.1：PPT 渲染改为可选并加超时，文档写明支持 WPS 生成的 .pptx、不引导安装 PowerPoint。
- 2026-10-13 首次推送到公开仓库前脱敏：模板换虚构数据、注册表 token 移到本地文件、风格文档去内部链接、旧 steering 不入库；回归 10/10。
