#!/usr/bin/env bash
# Mega Tunnel Iran preflight: READ ONLY. Prints no credentials / user IDs.
set -Eeuo pipefail
export LC_ALL=C
echo '=== MEGA IRAN READ-ONLY PREFLIGHT ==='
echo 'No services stopped/restarted; no packages installed; no configs written.'
printf 'UTC time: '; date -u '+%Y-%m-%d %H:%M:%SZ'
printf 'Hostname: '; hostname
printf 'Kernel: '; uname -sr
printf 'Architecture: '; uname -m
printf 'CPU count: '; nproc
echo '--- memory and CPU pressure ---'
free -h
for f in /proc/pressure/cpu /proc/pressure/memory /proc/pressure/io; do
  if [[ -r "$f" ]]; then printf '%s: ' "$f"; head -n 1 "$f"; fi
done
echo '--- x-ui precise version ---'
if [[ -x /usr/local/x-ui/x-ui ]]; then
  /usr/local/x-ui/x-ui -v 2>&1 | head -n 2 || true
else
  echo 'WARN: /usr/local/x-ui/x-ui unavailable; determine panel binary path manually'
fi
for svc in x-ui dual-trust-client dual-mieru-carrier dual-xudp-bridge dual-dispatcher; do
  printf 'Service %-25s ' "$svc"
  systemctl is-active "$svc.service" 2>/dev/null || true
done
echo '--- x-ui SQLite safe summary (read-only, no settings values) ---'
python3 - <<'PY'
import sqlite3
from pathlib import Path
p=Path('/etc/x-ui/x-ui.db')
if not p.is_file():
 print('WARN: x-ui DB not found at expected path')
else:
 try:
  conn=sqlite3.connect(f'file:{p}?mode=ro',uri=True,timeout=3)
  try:
   tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
   print("DB readable: YES")
   print("settings table:",'YES' if 'settings' in tables else 'NO')
   if 'settings' in tables:
    r=conn.execute("SELECT EXISTS(SELECT 1 FROM settings WHERE key='xrayTemplateConfig')").fetchone()
    print("xrayTemplateConfig present:", bool(r[0]))
   print("inbounds table:",'YES' if 'inbounds' in tables else 'NO')
  finally: conn.close()
 except Exception as e: print('DB inspection error:',type(e).__name__)
PY
echo '--- listening ports (no IP/credential output) ---'
for port in 443 7990 7991 7992 7993 7994 17990; do
  n=$(ss -H -ltn "( sport = :$port )" 2>/dev/null | wc -l)
  printf 'TCP %-5s listeners=%s\n' "$port" "$n"
done
echo '--- global TCP state ---'
ss -s | head -n 5 || true
echo '--- file descriptor ceiling ---'
cat /proc/sys/fs/file-max 2>/dev/null || true
echo '=== PREFLIGHT COMPLETE — NO MUTATION ==='
