# 贡献与维护规则

## 一、单一事实源
| 事项 | 事实源 |
|---|---|
| skill 行为、铁律、路由 | `skills/canvas-restyle/SKILL.md` |
| 通用视觉原则 | `references/principles.md` |
| 色系归类、色板、品牌色锚定、文字颜色规则 | `scripts/core/`（`palette.json` 与 `references/palette.md` 同步改） |
| 飞书执行流程 / 角色规则 / 检查器约束 | `references/adapters/feishu*.md`；角色规则实现在 `scripts/adapters/feishu/redraw.py` |
| PPT 执行流程与改色规则 | `references/adapters/pptx.md`；实现在 `scripts/adapters/pptx/plan.py` |
| 飞书模板版式 | `templates/<name>/gen.py` + `reference.svg`；说明在 `references/styles/<name>.md` |
| 项目状态 | `PROJECT_CONTEXT.md` |

## 二、改动顺序
1. 先在 `_runs/<运行>/` 里验证想法（不动引擎）。
2. 确认通用后再改 `scripts/` 或 `templates/`，同步对应说明文档。
   - 改 `scripts/core/` 会同时影响所有适配器，必须两边都回归。
   - 新增适配器：放 `scripts/adapters/<工具>/`，颜色决策只调用 `core`，在 `restyle.py` 加路由，写 `references/adapters/<工具>.md`。
3. 跑回归 `bash tests/regress.sh`，必须全部 PASS：
   - 飞书模板输出与 `reference.svg` **逐字节一致**；若有意改模板版式，重新生成 `reference.svg/png` 并在 CHANGELOG 说明。
   - `tests/cases.txt` 每块画板：check 0/0 + 文字一致。新增画板类型时把它的 raw 加进用例。
   - `tests/cases-pptx.txt` 每份 PPT：`verify.py` ok 且确有改动。新的 PPT 样本放 `_runs/fixtures/pptx/`。
   - 只做重构时，额外比对飞书 7 例输出与重构前逐字节一致（`_runs/baseline-*/`）。
4. 更新 `CHANGELOG.md`（面向 skill 使用者，只写能力变化）与 `PROJECT_CONTEXT.md`（面向维护者，写过程与结论）。

## 三、入库边界
- 入库：`skills/`、`tests/`、`docs/`、根目录治理文件、`.kiro/steering/`。
- 不入库：`_runs/`（含真实业务画板 / PPT、文档链接与 token）、`__pycache__/`、`.DS_Store`。真实业务 PPT 不要放进 `docs/`。
- skill 目录内不得出现：真实业务数据、用户本机绝对路径、文档链接以外的私有信息。
  远端是公开仓库：飞书内部链接、画板 token、真实业务数据一律不入库。
  基准画板 token / 链接写在 `templates/registry.local.json`（不入库）；模板数据段只放虚构示例。
  提交前 grep 一遍内部域名、20 位以上 token 与业务名称。

## 四、版本
`SKILL.md` 的 `version` 为唯一版本号，`x.y.z`：x 不兼容改动（铁律、路由、引擎选择规则）、y 新能力（新适配器、新角色、新模板）、z 修复。

## 五、协作约定
- 不替用户 `git commit` / `git push`。
- 原件只读：飞书只写新建画板；PPT 只写新文件。
