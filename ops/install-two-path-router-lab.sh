#!/usr/bin/env bash
# Isolated dual-carrier verified SOCKS router, Stage3 LAB ONLY on Maya1.
# Never edits x-ui, customer inbounds, foreign transports, firewall or routing.
set -Eeuo pipefail
[[ $(id -u) -eq 0 ]] || { echo "root required" >&2; exit 2; }
[[ $# -eq 1 && "$1" == maya1 ]] ||
 { echo "Usage: sudo bash ops/install-two-path-router-lab.sh maya1" >&2; exit 2; }
umask 077
BASE=/etc/mega-tunnel
DIR="$BASE/router-lab"
CONF="$DIR/maya1.json"
UNIT='mega-maya1-router-lab.service'
UNITPATH="/etc/systemd/system/$UNIT"
ROOT=/opt/mega-tunnel
[[ -d "$ROOT/.git" && -f "$ROOT/mega_tunnel/lab_proxy.py" &&
   -f "$ROOT/mega_tunnel/lab_health.py" ]] ||
 { echo "Git repo or Stage3 verified-probe router missing. Run git pull first." >&2; exit 1; }
[[ -f "$BASE/stage0.json" ]] || { echo "Stage0 Maya1 not installed" >&2; exit 1; }
python3 - "$BASE/stage0.json" <<'PY'
import json,sys
s=json.load(open(sys.argv[1]))
if s.get("kind")!="mega-tunnel-stage0" or s.get("role")!="maya1":
 raise SystemExit("STOP: this host is not registered as Maya1")
PY
[[ -x /usr/local/x-ui/x-ui ]] || { echo "Existing x-ui missing; STOP" >&2; exit 1; }
XV=$(/usr/local/x-ui/x-ui -v 2>/dev/null | tr -d '[:space:]' | sed 's/^v//')
[[ "$XV" == 2.9.4 ]] || { echo "Expected x-ui version 2.9.4; got $XV" >&2; exit 1; }
systemctl is-active --quiet x-ui.service || { echo "x-ui must be healthy; STOP" >&2; exit 1; }
for node in f1 f2; do
 case "$node" in
  f1) svc=mega-f1-naive-client.service; port=17995 ;;
  f2) svc=mega-f2-xhttp-client.service; port=17996 ;;
 esac
 systemctl is-active --quiet "$svc" ||
  { echo "Carrier service $svc inactive; STOP" >&2; exit 1; }
 ss -H -ltn "sport = :$port" | grep -Fq "127.0.0.1:$port" ||
  { echo "Carrier $node loopback SOCKS :$port not listening; STOP" >&2; exit 1; }
done
! ss -H -ltn '( sport = :17990 )' | grep -q . ||
 { echo "Port TCP/17990 occupied: cannot create lab router" >&2; exit 1; }
[[ ! -e "$DIR" && ! -e "$UNITPATH" ]] ||
 { echo "Existing router lab config/unit; refusing to overwrite; STOP" >&2; exit 1; }
id mega-tunnel >/dev/null || { echo "mega-tunnel restricted service user missing" >&2; exit 1; }
[[ $(stat -c %u "$BASE") == 0 ]] ||
 { echo "Unexpected stage0 base ownership" >&2; exit 1; }
chgrp mega-tunnel "$BASE"
chmod 0710 "$BASE"
install -d -o root -g mega-tunnel -m 0750 "$DIR"
python3 - "$CONF" <<'PY'
import json,os,sys
cfg={
 "lab_only":True,
 "gateway":"Maya1",
 "listen_host":"127.0.0.1",
 "listen_port":17990,
 "upstreams":{"F1":17995,"F2":17996}
}
fd=os.open(sys.argv[1],os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o640)
with os.fdopen(fd,"w") as f:
 json.dump(cfg,f,indent=2)
 f.write("\n")
PY
chown root:mega-tunnel "$CONF"
chmod 0640 "$CONF"
runuser -u mega-tunnel -- test -r "$CONF" ||
 { echo "Restricted router service user cannot read its config; STOP" >&2; exit 1; }
(
 cd "$ROOT"
 python3 -c 'from mega_tunnel.lab_proxy import parse_config; import sys; g,p,u=parse_config(sys.argv[1]); assert (g,p,u)==("Maya1",17990,{"F1":17995,"F2":17996})' "$CONF"
)
cat > "$UNITPATH" <<EOF
[Unit]
Description=Mega Tunnel Maya1 verified dual-carrier lab router (LOCAL ONLY)
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User=mega-tunnel
Group=mega-tunnel
WorkingDirectory=$ROOT
ExecStart=/usr/bin/python3 -m mega_tunnel.lab_proxy --lab-only --config $CONF
Environment=PYTHONDONTWRITEBYTECODE=1
Restart=on-failure
RestartSec=5
LimitNOFILE=4096
MemoryHigh=96M
MemoryMax=192M
TasksMax=96
Nice=5
NoNewPrivileges=true
ProtectHome=true
ProtectSystem=strict
PrivateTmp=true
[Install]
WantedBy=multi-user.target
EOF
chmod 0644 "$UNITPATH"
systemd-analyze verify "$UNITPATH" >/dev/null
systemctl daemon-reload
systemctl enable --now "$UNIT"
for _ in $(seq 1 18); do
 if systemctl is-active --quiet "$UNIT" &&
   ss -H -ltn '( sport = :17990 )' | grep -Fq '127.0.0.1:17990'; then
   break
 fi
 sleep 1
done
systemctl is-active --quiet "$UNIT" ||
 { echo "Lab router not active; inspect systemctl show and journalctl -u mega-maya1-router-lab" >&2; exit 1; }
ss -H -ltn '( sport = :17990 )' | grep -Fq '127.0.0.1:17990' ||
 { echo "Local-only router SOCKS listener not ready; inspect service logs" >&2; exit 1; }
echo "Lab router active ONLY on 127.0.0.1:17990; F1 and F2 remain independent."
echo "No x-ui user routes were edited. No customer migration."
echo "Next: sudo bash ops/test-two-path-router-lab.sh"
