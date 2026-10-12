# AGENTS.md

本仓库是 **canvas-restyle** skill 的开发仓库（飞书画板、PPT 等自由画布的样式优化）。

- **要优化一个画板或 PPT**：按 [`skills/canvas-restyle/SKILL.md`](skills/canvas-restyle/SKILL.md) 执行，产物写到 `_runs/`。
- **要改 skill 本身**：先读 `PROJECT_CONTEXT.md` 与 `CONTRIBUTING.md`，改完跑 `bash tests/regress.sh`。

铁律速记：原件只读，只写新画板 / 新文件；内容、文字、位置不变，只改样式；颜色决策统一走 `scripts/core/`；
按工具的完成标准校验（飞书 check 0/0 + 文字一致；PPT `verify.py` ok）；不替用户 git commit / push。

`_runs/` 下的 `b2–b6`、`wb*`、`hs` 是早期尝试，除非用户要求不要读取。大文件（raw.json、svg、pptx 内 XML）用 grep / 行范围读。
