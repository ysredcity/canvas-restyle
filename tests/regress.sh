#!/usr/bin/env bash
# 回归：改了 skill 的 scripts / templates 后运行。不写飞书，只用本地已导出的 raw。
#   1) 两个数据驱动模板：输出与 reference.svg 逐字节一致
#   2) 飞书 redraw.py 对 tests/cases.txt 里的每个 raw：check 0/0 + 文字多重集一致
#   3) PPT 适配器对 tests/cases-pptx.txt 里的每个文件：plan → apply → verify ok（只改颜色）且确有改动
# 用法：bash tests/regress.sh            （在仓库根目录执行）
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd); SK="$ROOT/skills/canvas-restyle"; S="$SK/scripts/adapters/feishu"
OUT=$(mktemp -d); FAIL=0
for t in "$SK"/templates/*/; do
  n=$(basename "$t"); [[ -f "$t/gen.py" ]] || continue
  d="$OUT/tpl-$n"; mkdir -p "$d"; cp "$t/gen.py" "$d/"
  (cd "$d" && python3 gen.py >/dev/null 2>&1)
  if cmp -s "$d/diagram.svg" "$t/reference.svg"; then echo "PASS template $n"; else echo "FAIL template $n（与 reference.svg 不一致）"; FAIL=1; fi
done
while read -r name raw; do
  [[ -z "$name" || "$name" == \#* ]] && continue
  [[ -f "$ROOT/$raw" ]] || { echo "SKIP $name（缺少 $raw）"; continue; }
  d="$OUT/$name"; mkdir -p "$d"
  python3 "$S/redraw.py" "$ROOT/$raw" -o "$d/diagram.svg" --report "$d/report.json" >/dev/null || { echo "FAIL $name（redraw 异常）"; FAIL=1; continue; }
  c=$(bash "$S/check.sh" "$d/diagram.svg" | head -1)
  v=$(python3 "$S/verify_text.py" "$ROOT/$raw" "$d/diagram.svg" | head -1)
  if [[ "$c" == "errors=0 warnings=0" && "$v" == *"missing=0 extra=0" ]]; then echo "PASS $name"; else echo "FAIL $name  [$c] [$v]"; FAIL=1; fi
done < "$ROOT/tests/cases.txt"
PP="$SK/scripts/adapters/pptx"
while read -r name f; do
  [[ -z "$name" || "$name" == \#* ]] && continue
  [[ -f "$ROOT/$f" ]] || { echo "SKIP ${name}（缺少 ${f}）"; continue; }
  d="$OUT/$name"; mkdir -p "$d"
  python3 "$PP/plan.py" "$ROOT/$f" -o "$d/plan.json" >/dev/null &&
  n=$(python3 "$PP/apply.py" "$ROOT/$f" "$d/plan.json" -o "$d/out.pptx" | python3 -c 'import sys,json;print(json.loads(sys.stdin.read().splitlines()[-1])["changed_refs"])') &&
  v=$(python3 "$PP/verify.py" "$ROOT/$f" "$d/out.pptx" | head -1)
  if [[ "$v" == ok* && "${n:-0}" -gt 0 ]]; then echo "PASS pptx ${name}（改动 ${n} 处）"; else echo "FAIL pptx $name  [$v] [changed=$n]"; FAIL=1; fi
done < "$ROOT/tests/cases-pptx.txt"
echo "输出目录：$OUT"
exit $FAIL
