#!/usr/bin/env bash
# Functional smoke/latency test only. Never changes x-ui, proxy config or services.
set -Eeuo pipefail
[[ $# -eq 1 ]] || { echo "Usage: bash ops/test-naive-lab.sh maya1|maya3" >&2; exit 2; }
case "$1" in
 maya1) ROLE=f1; PORT=17995 ;;
 maya3) ROLE=f3; PORT=17997 ;;
 *) echo 'Unsupported gateway' >&2; exit 2;;
esac
echo "=== Mega Tunnel Stage1 Naive TCP functional checks ($1 / $ROLE) ==="
GOOD=0
SUM=0
for i in $(seq 1 10); do
 RESULT=$(curl -4 -sS --socks5-hostname "127.0.0.1:$PORT" \
  --connect-timeout 6 --max-time 15 -o /dev/null \
  -w '%{http_code} %{time_total}' \
  https://www.gstatic.com/generate_204 2>/dev/null || true)
 CODE=$(echo "$RESULT" | awk '{print $1}')
 SECS=$(echo "$RESULT" | awk '{print $2}')
 printf 'Try %2s: HTTP %-3s total=%ss\n' "$i" "$CODE" "$SECS"
 if [[ "$CODE" == 204 ]]; then GOOD=$((GOOD+1)); fi
 sleep 1
done
echo "Successful Google 204 probes: $GOOD / 10"
RESULT=$(curl -4 -sS --socks5-hostname "127.0.0.1:$PORT" \
 --connect-timeout 6 --max-time 15 -o /dev/null \
 -w 'HTTP=%{http_code} TIME=%{time_total}s' \
 https://example.com/ 2>/dev/null || true)
echo "Secondary HTTPS test: $RESULT"
RESULT=$(curl -4 -sS --socks5-hostname "127.0.0.1:$PORT" \
 --connect-timeout 6 --max-time 15 -o /dev/null \
 -w 'HTTP=%{http_code} TIME=%{time_total}s' \
 https://api.telegram.org/ 2>/dev/null || true)
echo "Telegram API HTTPS test: $RESULT (non-200 may be normal)"
echo "=== Runtime and Memory ==="
systemctl show "mega-$ROLE-naive-client.service" \
 -p ActiveState -p MemoryCurrent -p NRestarts --no-pager
free -h
vmware-toolbox-cmd stat balloon 2>/dev/null || true
echo '=== END ==='
if (( GOOD < 8 )); then
 echo 'WARN: 8/10 TCP probe threshold failed; do not attach clients.' >&2
 exit 1
fi
echo 'OK: only isolated TCP test passed. UDP, XHTTP and 290-user load are NOT verified.'
