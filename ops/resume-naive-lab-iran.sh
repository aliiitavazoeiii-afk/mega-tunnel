#!/usr/bin/env bash
# Resume interrupted Mega Tunnel Stage-1 Naive-only lab on Maya1/Maya3.
# No package installs, no network downloads, no x-ui changes, no config overwrites.
set -Eeuo pipefail
[[ $(id -u) -eq 0 ]] || { echo 'root required' >&2; exit 2; }
[[ $# -eq 2 ]] || { echo 'Usage: sudo bash ops/resume-naive-lab-iran.sh maya1|maya3 /root/mega-f1-naive-client.json' >&2; exit 2; }
GATEWAY=$1; BUNDLE=$2
case "$GATEWAY" in
 maya1) ROLE=f1; PORT=17995 ;;
 maya3) ROLE=f3; PORT=17997 ;;
 *) echo 'Unsupported gateway' >&2; exit 2;;
esac
D="/etc/mega-tunnel/naive-$ROLE"
BIN='/usr/local/lib/mega-tunnel/naive-v154'
UNIT="mega-$ROLE-naive-client.service"
UNIT_PATH="/etc/systemd/system/$UNIT"
CFG="$D/client.json"
BASE='/etc/mega-tunnel'
umask 077
[[ -d "$D" && -s "$BUNDLE" ]] || { echo 'Existing partial directory or private foreign bundle missing; stopping without changes' >&2; exit 1; }
[[ -x "$BIN" ]] || { echo "Pinned Naive executable missing at $BIN; no download attempted" >&2; exit 1; }
[[ -x /usr/local/x-ui/x-ui ]] || { echo 'x-ui binary missing; not touching panel' >&2; exit 1; }
XV=$(/usr/local/x-ui/x-ui -v 2>/dev/null | tr -d '[:space:]' | sed 's/^v//')
[[ "$XV" == '2.9.4' ]] || { echo "Expected x-ui 2.9.4; detected $XV. Not changing x-ui." >&2; exit 1; }
[[ $(stat -c %u "$BASE") == 0 && $(stat -c %u "$D") == 0 ]] || { echo 'Unsafe ownership of existing configuration directory' >&2; exit 1; }
python3 - "$BASE/stage0.json" "$BUNDLE" "$CFG" "$ROLE" "$PORT" <<'PY'
import ipaddress,json,pathlib,re,sys
stage,bundle,config,role,port=sys.argv[1:]
def obj(path):
    return json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
st=obj(stage)
if st.get('kind')!='mega-tunnel-stage0' or st.get('role')!=('maya1' if role=='f1' else 'maya3'):
    raise SystemExit('Wrong stage0 host role; refusing changes')
b=obj(bundle)
if b.get('version')!=1 or b.get('kind')!='mega-naive-lab' or b.get('foreign_id')!=role.upper() or b.get('port')!=443:
    raise SystemExit('Wrong/malformed private foreign bundle')
if not ipaddress.IPv4Address(b['public_ip']).is_global:
    raise SystemExit('Invalid foreign IPv4')
if not re.fullmatch(r'(?=.{4,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}', b['domain']):
    raise SystemExit('Invalid foreign domain')
if not re.fullmatch(r'meg-'+role+r'-[a-f0-9]{8}',b['username']) or not re.fullmatch(r'[a-f0-9]{64}',b['password']):
    raise SystemExit('Foreign bundle credentials in unexpected format')
expected={
    'listen':f'socks://127.0.0.1:{port}',
    'proxy':f"https://{b['username']}:{b['password']}@{b['domain']}",
    'host-resolver-rules':f"MAP {b['domain']} {b['public_ip']}"
}
c=pathlib.Path(config)
if c.exists():
    if c.is_symlink() or not c.is_file(): raise SystemExit('Existing config is not a regular file')
    if obj(config)!=expected:
        raise SystemExit('Existing client.json differs from supplied F1 bundle. STOP, do not overwrite')
    print('Existing Naive client config matches private F1 bundle: PASS')
else:
    c.parent.mkdir(mode=0o750,parents=True,exist_ok=True)
    with c.open('x',encoding='utf-8') as f:
        json.dump(expected,f,indent=2)
    c.chmod(0o600)
    print('Missing Naive client config safely created')
PY
if ! id mega-tunnel >/dev/null 2>&1; then
 useradd --system --no-create-home --shell /usr/sbin/nologin mega-tunnel
fi
chgrp mega-tunnel "$BASE" "$D"
chmod 0710 "$BASE"
chmod 0750 "$D"
[[ -f "$CFG" && ! -L "$CFG" && $(stat -c %u "$CFG") == 0 ]] || { echo 'Unsafe config owner or type' >&2; exit 1; }
chown root:mega-tunnel "$CFG"
chmod 0640 "$CFG"
runuser -u mega-tunnel -- test -r "$CFG" || { echo 'Service user cannot read config' >&2; exit 1; }
echo 'Restricted service access to existing configuration: PASS'
if [[ -e "$UNIT_PATH" ]]; then
 [[ -f "$UNIT_PATH" && ! -L "$UNIT_PATH" && $(stat -c %u "$UNIT_PATH") == 0 ]] || {
  echo 'Unsafe existing unit type/owner; refusing to modify' >&2; exit 1;
 }
 grep -Fxq 'User=mega-tunnel' "$UNIT_PATH" &&
 grep -Fxq 'Group=mega-tunnel' "$UNIT_PATH" &&
 grep -Fxq "ExecStart=$BIN $CFG" "$UNIT_PATH" || {
  echo 'Existing service unit differs from expected path/account; refusing to alter it' >&2; exit 1;
 }
 echo 'Existing systemd unit verified; preserving it'
else
 cat > "$UNIT_PATH" <<EOF
[Unit]
Description=Mega Tunnel Naive TCP lab $GATEWAY -> $ROLE
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User=mega-tunnel
Group=mega-tunnel
ExecStart=$BIN $CFG
Restart=on-failure
RestartSec=3
LimitNOFILE=65536
MemoryHigh=96M
MemoryMax=192M
Nice=5
NoNewPrivileges=true
ProtectHome=true
ProtectSystem=strict
PrivateTmp=true
[Install]
WantedBy=multi-user.target
EOF
 chmod 0644 "$UNIT_PATH"
 echo 'Missing systemd unit safely created'
fi
systemd-analyze verify "$UNIT_PATH" >/dev/null
systemctl daemon-reload
if systemctl is-active --quiet "$UNIT"; then
 echo "Service already active, preserving current connections"
else
 # Clear a prior crash/restart loop of ONLY this lab unit. No x-ui action.
 systemctl stop "$UNIT" 2>/dev/null || true
 if ss -H -ltn "sport = :$PORT" | grep -q .; then
   echo "Local TCP port $PORT is already occupied by another process; STOP" >&2; exit 1
 fi
 systemctl reset-failed "$UNIT" 2>/dev/null || true
 systemctl enable --now "$UNIT"
fi
for _ in $(seq 1 6); do
 if ss -H -ltn "sport = :$PORT" | grep -q .; then break; fi
 sleep 1
done
if ! systemctl is-active --quiet "$UNIT"; then
 echo "Lab service failed to stay active; inspect safe diagnostics (avoid printing config)" >&2
 systemctl show "$UNIT" -p ActiveState -p ExecMainStatus -p NRestarts --no-pager
 exit 1
fi
if ! ss -H -ltn "sport = :$PORT" | grep -q '127\.0\.0\.1:'; then
 echo "Expected loopback-only SOCKS port $PORT not listening; refusing to claim success" >&2; exit 1
fi
echo '=== END-TO-END TCP THROUGH F1 LAB ==='
OK=0
for i in 1 2 3 4 5; do
 CODE=$(curl -4 --proxy "socks5h://127.0.0.1:$PORT" --noproxy '' \
  -sS --connect-timeout 6 --max-time 15 -o /dev/null -w '%{http_code}' \
  https://www.gstatic.com/generate_204 2>/dev/null || true)
 echo "Through F1 try $i/5: HTTP $CODE"
 [[ "$CODE" == 204 ]] && OK=$((OK+1))
 sleep 1
done
echo "Passed $OK/5"
echo '=== SERVICE AND MEMORY ==='
systemctl show "$UNIT" -p ActiveState -p ExecMainStatus -p NRestarts -p MemoryCurrent --no-pager
free -h
if (( OK < 4 )); then
 echo 'LAB NOT VERIFIED: no changes to x-ui; keep SOCKS isolated and share non-secret diagnostic output' >&2
 exit 1
fi
echo 'SUCCESS: isolated encrypted Naive TCP F1 lab verified; x-ui routing unchanged.'
