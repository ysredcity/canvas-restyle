#!/usr/bin/env bash
# 回归：改了 skill 的 scripts / templates 后运行。不写飞书，只用本地已导出的 raw。
#   1) 两个数据驱动模板：输出与 reference.svg 逐字节一致
#   2) 飞书 redraw.py 对 tests/cases.txt 里的每个 raw：保守档与基线逐字节一致 + 目标档 check 0/0 且文字多重集一致
#   3) review_image.py：完整原图不变，review 最长边 <2000；有 Pillow 时切片也全部 <2000
#   4) PPT 适配器对 tests/cases-pptx.txt 里的每个文件：plan → apply → verify ok（只改颜色）且确有改动
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
while read -r name raw mode; do
  [[ -z "$name" || "$name" == \#* ]] && continue
  [[ -f "$ROOT/$raw" ]] || { echo "SKIP ${name}（缺少 ${raw}）"; continue; }
  mode="${mode:-standard}"
  d="$OUT/$name"; mkdir -p "$d"
  # 1) 保守档：只改配色，必须与基线逐字节一致（基线不存在则只要求能跑通）
  python3 "$S/redraw.py" "$ROOT/$raw" -o "$d/c.svg" --mode conservative >/dev/null || { echo "FAIL ${name}（conservative 异常）"; FAIL=1; continue; }
  base="$ROOT/_runs/baseline-1.0.1/$name.svg"
  if [[ -f "$base" ]] && ! cmp -s "$d/c.svg" "$base"; then echo "FAIL ${name}（conservative 与基线不一致）"; FAIL=1; fi
  # 2) 目标档：check 0/0 + 文字一致
  python3 "$S/redraw.py" "$ROOT/$raw" -o "$d/diagram.svg" --report "$d/report.json" --mode "$mode" >/dev/null || { echo "FAIL ${name}（$mode 异常）"; FAIL=1; continue; }
  c=$(bash "$S/check.sh" "$d/diagram.svg" | head -1)
  v=$(python3 "$S/verify_text.py" "$ROOT/$raw" "$d/diagram.svg" | head -1)
  if [[ "$c" == "errors=0 warnings=0" && "$v" == *"missing=0 extra=0" ]]; then echo "PASS ${name}（${mode}）"; else echo "FAIL ${name}  [$c] [$v]"; FAIL=1; fi
done < "$ROOT/tests/cases.txt"
# 模型查看副本：原图不变，review / 切片严格小于 2000px
RV="$SK/scripts/core/review_image.py"; SAMPLE="$SK/templates/ops-board/reference.png"
d="$OUT/review-image"; mkdir -p "$d"; before=$(shasum -a 256 "$SAMPLE" | awk '{print $1}')
result=$(python3 "$RV" "$SAMPLE" -o "$d/reference.review.png" 2>/dev/null)
after=$(shasum -a 256 "$SAMPLE" | awk '{print $1}')
if [[ "$before" == "$after" ]] && python3 - "$result" <<'PY'
import json, sys
x = json.loads(sys.argv[1]); w, h = x['review_size']
assert max(w, h) < 2000 and x['out'].endswith('.review.png')
PY
then echo "PASS review image（最长边 <2000，原图不变）"; else echo "FAIL review image"; FAIL=1; fi
if python3 -c 'import PIL' >/dev/null 2>&1; then
  tiles=$(python3 "$RV" "$SAMPLE" -o "$d/tiled.review.png" --tiles-dir "$d/tiles" 2>/dev/null)
  if python3 - "$tiles" <<'PY'
import json, sys
x = json.loads(sys.argv[1]); assert len(x['tiles']) > 1
assert all(max(t['size']) < 2000 for t in x['tiles'])
PY
  then echo "PASS review tiles（逐张 <2000）"; else echo "FAIL review tiles"; FAIL=1; fi
fi
if python3 "$RV" "$SAMPLE" --max 2000 -o "$d/invalid.png" >/dev/null 2>&1; then
  echo "FAIL review limit（应拒绝 2000）"; FAIL=1
else
  echo "PASS review limit（拒绝 >=2000）"
fi
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
