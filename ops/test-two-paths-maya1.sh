#!/usr/bin/env bash
# Non-disruptive dual-carrier sequential TCP smoke test on Maya1 only.
set -Eeuo pipefail
echo "=== MAYA1 ISOLATED TWO-PATH TCP CHECK ==="
for item in "F1:17995:mega-f1-naive-client" "F2:17996:mega-f2-xhttp-client"; do
 IFS=: read -r LABEL PORT SERVICE <<<"$item"
 echo "--- $LABEL TCP via local 127.0.0.1:$PORT ---"
 systemctl show "$SERVICE" -p ActiveState -p NRestarts -p MemoryCurrent --no-pager
 good=0
 for i in 1 2 3 4 5; do
  code=$(curl -4 --proxy "socks5h://127.0.0.1:$PORT" \
   --noproxy '' --connect-timeout 8 --max-time 20 \
   -sS -o /dev/null -w '%{http_code}' \
   https://www.gstatic.com/generate_204 2>/dev/null || true)
  echo "$LABEL request $i/5: HTTP $code"
  [[ "$code" == 204 ]] && good=$((good+1))
  sleep 1
 done
 echo "$LABEL: $good/5 HTTP 204 via real carrier"
 if (( good < 4 )); then
  echo "WARN: $LABEL unreliable; no routing changes were made"
 fi
done
echo "--- Host RAM ---"
free -h
vmware-toolbox-cmd stat balloon 2>/dev/null || true
echo "=== LAB ONLY: No x-ui user traffic, failover, XUDP or load tested ==="
