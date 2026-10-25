#!/usr/bin/env bash
# Mega Tunnel Stage2 Maya1->F2 or Maya3->F4 XHTTP+REALITY TCP lab.
# No downloads, no package upgrades, no x-ui edits or service restarts.
set -Eeuo pipefail
[[ $(id -u) -eq 0 && $# -eq 3 ]] ||
 { echo "Usage: sudo bash ops/install-xhttp-lab-iran.sh maya1|maya3 /root/mega-f2-xhttp-client.json /root/mega-f2-xray-bin" >&2; exit 2; }
GATEWAY=$1; BUNDLE=$2; TRANSFERRED=$3
case "$GATEWAY" in
 maya1) ROLE=f2; PORT=17996 ;;
 maya3) ROLE=f4; PORT=17998 ;;
 *) echo "Unsupported gateway" >&2; exit 2;;
esac
BASE=/etc/mega-tunnel
D="$BASE/xhttp-$ROLE"
LIB=/usr/local/lib/mega-tunnel
BIN="$LIB/xray-v26.9.30"
UNIT="mega-$ROLE-xhttp-client.service"
umask 077
[[ -s "$BUNDLE" && -s "$TRANSFERRED" && -d "$BASE" ]] ||
 { echo "Foreign private bundle, verified Xray binary, or stage0 not found" >&2; exit 1; }
[[ ! -e "$D" && ! -e "/etc/systemd/system/$UNIT" ]] ||
 { echo "Existing F2/F4 configuration detected; refusing overwrite" >&2; exit 1; }
[[ -x /usr/local/x-ui/x-ui ]] ||
 { echo "x-ui must already be installed; no x-ui mutation" >&2; exit 1; }
XV=$(/usr/local/x-ui/x-ui -v 2>/dev/null | tr -d '[:space:]' | sed 's/^v//')
[[ "$XV" == '2.9.4' ]] || { echo "x-ui version mismatch ($XV); STOP" >&2; exit 1; }
systemctl is-active --quiet x-ui.service || { echo "x-ui inactive; STOP" >&2; exit 1; }
! ss -H -ltn "sport = :$PORT" | grep -q . ||
 { echo "Local lab SOCKS port $PORT occupied" >&2; exit 1; }
python3 - "$BASE/stage0.json" "$BUNDLE" "$TRANSFERRED" "$GATEWAY" "$ROLE" <<'PY'
import hashlib,ipaddress,json,pathlib,re,sys,uuid
stage,bundle,exe,gateway,role=sys.argv[1:]
s=json.loads(pathlib.Path(stage).read_text())
if s.get('kind')!='mega-tunnel-stage0' or s.get('role')!=gateway:
 raise SystemExit("Wrong stage0 role; STOP")
b=json.loads(pathlib.Path(bundle).read_text())
if b.get("kind")!="mega-xhttp-reality-lab" or b.get("version")!=1 or b.get("foreign_id")!=role.upper():
 raise SystemExit("Wrong foreign XHTTP bundle; STOP")
if b.get("xray_release")!="v26.9.30" or b.get("transport")!="tcp-xhttp-stream-one-reality":
 raise SystemExit("Wrong binary version/transport")
if b.get("port")!=443 or not ipaddress.IPv4Address(b["public_ip"]).is_global:
 raise SystemExit("Invalid remote port/public IP")
uuid.UUID(b["uuid"])
checks=[
 (r'[A-Za-z0-9_-]{43,44}',b["public_key"]),
 (r'[a-f0-9]{16}',b["short_id"]),
 (r'/m-[a-f0-9]{24}',b["xhttp_path"]),
 (r'(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}',b["reality_server_name"]),
 (r'[a-f0-9]{64}',b["xray_binary_sha256"])
]
if any(re.fullmatch(regex,v) is None for regex,v in checks):
 raise SystemExit("Invalid REALITY bundle field")
if pathlib.Path(exe).is_symlink() or not pathlib.Path(exe).is_file():
 raise SystemExit("Transferred Xray must be regular file")
digest=hashlib.sha256(pathlib.Path(exe).read_bytes()).hexdigest()
if digest!=b["xray_binary_sha256"]:
 raise SystemExit("Transferred Xray SHA256 differs from verified foreign binary")
print("REALITY identity, transported binary digest, port and stage0 role: PASS")
PY
[[ $(stat -c %u "$BASE") == 0 ]] ||
 { echo "Unexpected stage0 owner" >&2; exit 1; }
if ! id mega-tunnel >/dev/null 2>&1; then
 useradd --system --no-create-home --shell /usr/sbin/nologin mega-tunnel
fi
install -d -m 0755 "$LIB"
if [[ -e "$BIN" ]]; then
 cmp -s "$BIN" "$TRANSFERRED" ||
  { echo "Existing Xray v26.9.30 differs from verified F2 binary; STOP" >&2; exit 1; }
else
 install -m 0755 "$TRANSFERRED" "$BIN"
fi
chgrp mega-tunnel "$BASE"
chmod 0710 "$BASE"
install -d -o root -g mega-tunnel -m 0750 "$D"
python3 - "$BUNDLE" "$D/client.json" "$PORT" <<'PY'
import json,os,sys
bundle_path,conf_path,port=sys.argv[1:]
b=json.load(open(bundle_path))
cfg={
 "log":{"loglevel":"warning"},
 "inbounds":[{
   "tag":"f2-socks-in","listen":"127.0.0.1",
   "port":int(port),"protocol":"socks",
   "settings":{"auth":"noauth","udp":False}
 }],
 "outbounds":[{
   "tag":"xhttp-reality-f2","protocol":"vless",
   "settings":{"address":b["public_ip"],"port":443,
       "id":b["uuid"],"encryption":"none","flow":""},
   "streamSettings":{
      "network":"xhttp",
      "xhttpSettings":{"path":b["xhttp_path"],"mode":"stream-one"},
      "security":"reality",
      "realitySettings":{"serverName":b["reality_server_name"],
        "publicKey":b["public_key"],"shortId":b["short_id"],
        "fingerprint":"chrome","spiderX":"/"}}
  },{
   "tag":"block","protocol":"blackhole"
  }],
 "routing":{"domainStrategy":"AsIs",
   "rules":[{"type":"field","inboundTag":["f2-socks-in"],
             "network":"udp","outboundTag":"block"}]}
}
fd=os.open(conf_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o640)
with os.fdopen(fd,"w") as f: json.dump(cfg,f,indent=2)
PY
chown root:mega-tunnel "$D/client.json"
chmod 0640 "$D/client.json"
runuser -u mega-tunnel -- test -r "$D/client.json" ||
 { echo "Unprivileged Xray user cannot read config" >&2; exit 1; }
"$BIN" run -test -c "$D/client.json" >/dev/null ||
 { echo "Xray config invalid; stopping before creating unit" >&2; exit 1; }
cat > "/etc/systemd/system/$UNIT" <<EOF
[Unit]
Description=Mega Tunnel XHTTP+REALITY TCP lab $GATEWAY -> $ROLE
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User=mega-tunnel
Group=mega-tunnel
ExecStart=$BIN run -c $D/client.json
Restart=on-failure
RestartSec=3
MemoryHigh=128M
MemoryMax=300M
LimitNOFILE=65536
Nice=5
NoNewPrivileges=true
ProtectHome=true
ProtectSystem=strict
PrivateTmp=true
[Install]
WantedBy=multi-user.target
EOF
systemd-analyze verify "/etc/systemd/system/$UNIT" >/dev/null
systemctl daemon-reload
systemctl enable --now "$UNIT"
for i in $(seq 1 12); do
 if systemctl is-active --quiet "$UNIT" &&
     ss -H -ltn "sport = :$PORT" | grep -q "127.0.0.1:$PORT"; then
   break
 fi
 sleep 1
done
systemctl is-active --quiet "$UNIT" ||
 { echo "XHTTP client not active; see unit status only" >&2; exit 1; }
ss -H -ltn "sport = :$PORT" | grep -q "127.0.0.1:$PORT" ||
 { echo "TCP SOCKS not listening locally" >&2; exit 1; }
echo "=== XHTTP+REALITY REAL END-TO-END TCP LAB ==="
OK=0
for i in 1 2 3 4 5; do
 CODE=$(curl -4 --noproxy '' --proxy "socks5h://127.0.0.1:$PORT" \
  -sS --connect-timeout 8 --max-time 20 -o /dev/null -w '%{http_code}' \
  https://www.gstatic.com/generate_204 2>/dev/null || true)
 echo "F2 via TCP XHTTP: $i/5 HTTP $CODE"
 [[ "$CODE" == 204 ]] && OK=$((OK+1))
 sleep 1
done
echo "Passed $OK/5"
systemctl show "$UNIT" -p ActiveState -p NRestarts -p MemoryCurrent --no-pager
free -h
if (( OK < 4 )); then
 echo "F2 LAB NOT VERIFIED: keep F1 and x-ui untouched; investigate only F2" >&2
 exit 1
fi
echo "SUCCESS: real TCP-only XHTTP+REALITY F2 lab path; no x-ui routing changed."
