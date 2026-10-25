#!/usr/bin/env bash
# Only a small non-intrusive end-to-end check via loopback :17990.
# Router monitor independently verifies F1/F2 via TLS/HTTP probes.
set -Eeuo pipefail
systemctl is-active --quiet mega-maya1-router-lab.service ||
 { echo "Router lab service inactive; STOP" >&2; exit 1; }
ss -H -ltn '( sport = :17990 )' | grep -Fq '127.0.0.1:17990' ||
 { echo "Lab router localhost :17990 not listening; STOP" >&2; exit 1; }
echo "=== LOCAL VERIFIED-CARRIER ROUTER 127.0.0.1:17990 ==="
passed=0
for i in $(seq 1 10); do
 result=$(curl -4 --noproxy '' --proxy socks5h://127.0.0.1:17990 \
  -sS --connect-timeout 7 --max-time 20 \
  -o /dev/null -w 'HTTP=%{http_code} TIME=%{time_total}s' \
  https://www.gstatic.com/generate_204 2>/dev/null || true)
 echo "Router request $i/10: $result"
 [[ "$result" == HTTP=204* ]] && passed=$((passed+1))
 sleep 1
done
echo "Healthy verified routing tests: $passed / 10"
echo "=== ISOLATED SERVICE STATES ==="
for svc in mega-f1-naive-client mega-f2-xhttp-client mega-maya1-router-lab x-ui; do
 echo "-- $svc --"
 systemctl show "$svc" -p ActiveState -p NRestarts -p MemoryCurrent --no-pager
done
echo "=== RAM ==="
free -h
vmware-toolbox-cmd stat balloon 2>/dev/null || true
if (( passed < 8 )); then
 echo "ROUTER LAB NOT VERIFIED: keep x-ui untouched; check carrier state logs" >&2
 exit 1
fi
echo "PASS: local router HTTPS flow test. This is NOT load balancing/failover production acceptance."
echo "No users migrated. Failover affects only NEW SOCKS TCP flows."
