#!/usr/bin/env bash
# Safe repair for completed-but-TLS-not-ready F1/F3 Naive lab foreign.
# Fixes only root parent traversal, restarts only the specified foreign lab
# service, validates real TLS and creates first private bundle.
set -Eeuo pipefail
[[ $(id -u) -eq 0 ]] || { echo "root required" >&2; exit 2; }
[[ $# -eq 1 ]] || { echo "Usage: sudo bash ops/repair-naive-lab-foreign.sh f1|f3" >&2; exit 2; }
ROLE=$1
case "$ROLE" in f1|f3) ;; *) echo "Unsupported role" >&2; exit 2;; esac
SERVICE="mega-$ROLE-naive-foreign.service"
D="/etc/mega-tunnel/naive-$ROLE"
STATE="/var/lib/mega-tunnel/naive-$ROLE"
BUNDLE="/root/mega-$ROLE-naive-client.json"
CONF="$D/Caddyfile"
[[ -f "$CONF" && -f "/etc/systemd/system/$SERVICE" && -d "$STATE" ]] ||
 { echo "Existing installation incomplete; STOP for review" >&2; exit 1; }
[[ ! -e "$BUNDLE" ]] || { echo "Private bundle already exists. Refusing to overwrite. Verify existing state." >&2; exit 1; }
id mega-tunnel >/dev/null || { echo "service user missing" >&2; exit 1; }
for parent in /etc/mega-tunnel /var/lib/mega-tunnel; do
 [[ -d "$parent" && $(stat -c %u "$parent") == 0 ]] ||
   { echo "Unexpected parent permissions: $parent" >&2; exit 1; }
 chgrp mega-tunnel "$parent"
 chmod 0710 "$parent"
done
runuser -u mega-tunnel -- test -r "$CONF" ||
 { echo "service user cannot read foreign config" >&2; exit 1; }
runuser -u mega-tunnel -- test -w "$STATE/data" ||
 { echo "service user cannot write TLS data path" >&2; exit 1; }
runuser -u mega-tunnel -- test -w "$STATE/config" ||
 { echo "service user cannot write TLS config path" >&2; exit 1; }
echo "Foreign service directory traversal: FIXED; private file permissions preserved"
# Keep accidental logs free of secrets: never print the Caddyfile itself.
systemctl stop "$SERVICE"
systemctl reset-failed "$SERVICE"
systemctl start "$SERVICE"
sleep 3
if ! systemctl is-active --quiet "$SERVICE"; then
 echo "Service still failing. Check: journalctl -u $SERVICE -n 35 --no-pager" >&2
 exit 1
fi
# The hostname and email were already recorded in validated local Caddyfile.
# Extract only validly shaped values; do not print proxy username/password.
DOMAIN=$(python3 - "$CONF" <<'PY'
import re,sys
s=open(sys.argv[1]).read()
hits=re.findall(r'(?m)^([A-Za-z0-9.-]+\.[A-Za-z]{2,})\s*\{\s*$',s)
if len(hits)!=1: raise SystemExit("Expected exactly one HTTPS hostname")
print(hits[0])
PY
)
READY=0
for i in $(seq 1 30); do
 if curl -4 -fsS --connect-timeout 4 --max-time 8 \
   --resolve "$DOMAIN:443:127.0.0.1" -o /dev/null "https://$DOMAIN/"; then
    READY=1; break
 fi
 systemctl is-active --quiet "$SERVICE" ||
   { echo "Service exited during TLS setup" >&2; exit 1; }
 sleep 2
done
(( READY == 1 )) || { echo "Service runs, but valid trusted TLS not ready; check DNS/firewall/ACME" >&2; exit 1; }
echo "F1/F3 Naive Caddy: active. Trusted HTTPS certificate test: PASS"
read -r -p 'Enter this foreign public IPv4 to finish private bundle: ' FOREIGN_IP
python3 - "$CONF" "$BUNDLE" "$ROLE" "$DOMAIN" "$FOREIGN_IP" <<'PY'
import ipaddress,json,os,re,socket,sys
path,bundle,role,domain,ip=sys.argv[1:]
addr=ipaddress.IPv4Address(ip)
if not addr.is_global: raise SystemExit("IPv4 must be globally routable")
dns={a[4][0] for a in socket.getaddrinfo(domain,None,family=socket.AF_INET)}
if ip not in dns: raise SystemExit("DNS A mismatch")
s=open(path,encoding='utf-8').read()
matches=re.findall(r'(?m)^\s*basic_auth\s+(\S+)\s+(\S+)\s*$',s)
if len(matches)!=1: raise SystemExit("Expected exactly one Naive basic_auth entry")
username,password=matches[0]
if not re.fullmatch(r'meg-'+re.escape(role)+r'-[0-9a-f]{8}',username):
 raise SystemExit("Unexpected Naive username")
if not re.fullmatch(r'[0-9a-f]{64}',password):
 raise SystemExit("Unexpected password shape")
data={"version":1,"kind":"mega-naive-lab","foreign_id":role.upper(),
      "public_ip":ip,"domain":domain,"port":443,
      "username":username,"password":password}
fd=os.open(bundle,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,"w") as f: json.dump(data,f,indent=2)
PY
echo "SUCCESS: $ROLE recovered and private client bundle created."
echo "Bundle location: $BUNDLE. Never paste its content or Caddyfile into chat."
echo "No x-ui changes, no foreign reprovisioning."
