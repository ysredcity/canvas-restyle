#!/usr/bin/env bash
# 用 whiteboard-cli 检查 SVG：只输出 errors / warnings 与问题摘要；可选渲染 PNG。
# 用法：check.sh diagram.svg [--png]
# 退出码：0 = errors=0 且 warnings=0；1 = 有问题；2 = 调用失败
set -uo pipefail
SVG="${1:?用法: check.sh diagram.svg [--png]}"
CLI=(npx -y "@larksuite/whiteboard-cli@^0.2.13")
OUT=$("${CLI[@]}" -i "$SVG" -f svg --check 2>&1)   # 有问题时 CLI 也以非零退出，统一在下面解析
python3 - "$OUT" <<'PY'
import json, re, sys
s = sys.argv[1]
m = re.search(r'\{.*\}', s, re.S)
if not m: print(s[-600:]); sys.exit(2)
d = json.loads(m.group(0))
def find(o, k):
    if isinstance(o, dict):
        if k in o: return o[k]
        for v in o.values():
            r = find(v, k)
            if r is not None: return r
    return None
e, w, iss = find(d, 'errors') or 0, find(d, 'warnings') or 0, find(d, 'issues') or []
print(f'errors={e} warnings={w}')
for i in iss[:15]: print(f"  - {i.get('type')} {i.get('nodeId')}: {i.get('message')}")
sys.exit(0 if (e == 0 and w == 0) else 1)
PY
RC=$?
if [[ "${2:-}" == "--png" ]]; then
  "${CLI[@]}" -i "$SVG" -f svg -o "${SVG%.svg}.png" >/dev/null 2>&1 && echo "png: ${SVG%.svg}.png"
fi
exit $RC
