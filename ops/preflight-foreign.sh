#!/usr/bin/env bash
# Read-only diagnostics for a prospective foreign node. Does not install or open ports.
set -Eeuo pipefail
export LC_ALL=C
echo '=== MEGA FOREIGN READ-ONLY PREFLIGHT ==='
printf 'UTC: '; date -u '+%Y-%m-%d %H:%M:%SZ'
printf 'Architecture: '; uname -m
printf 'Kernel: '; uname -sr
printf 'CPU: '; nproc
free -h
echo '--- support tools ---'
for bin in python3 curl openssl systemctl ss jq git; do
 if command -v "$bin" >/dev/null 2>&1; then
   printf '%s: available\n' "$bin"
 else
   printf '%s: missing\n' "$bin"
 fi
done
echo '--- privilege and port conflicts ---'
printf 'Current UID: '; id -u
for port in 443 8443 17990; do
 n=$(ss -H -ltn "( sport = :$port )" 2>/dev/null | wc -l)
 printf 'TCP %-5s listeners=%s\n' "$port" "$n"
done
echo '--- network counters ---'
python3 - <<'PY'
from pathlib import Path
for d in Path('/sys/class/net').iterdir():
 if d.name=='lo' or not (d/'statistics').exists(): continue
 print('interface:',d.name)
 for k in ('rx_errors','tx_errors','rx_dropped','tx_dropped'):
  try: print(' ',k, (d/'statistics'/k).read_text().strip())
  except OSError: pass
PY
echo '=== PREFLIGHT COMPLETE — NO MUTATION ==='
