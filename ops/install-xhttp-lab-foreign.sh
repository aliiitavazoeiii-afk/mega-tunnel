#!/usr/bin/env bash
# Mega Tunnel Stage2 lab: real VLESS + XHTTP stream-one + REALITY TCP foreign.
# Fresh, dedicated F2 or F4 x86_64 only. Does not touch x-ui or F1/F3.
set -Eeuo pipefail
[[ $(id -u) -eq 0 && $# -eq 1 ]] || { echo "Usage: sudo bash ops/install-xhttp-lab-foreign.sh f2|f4" >&2; exit 2; }
ROLE=$1
case "$ROLE" in f2|f4) ;; *) echo "Unsupported role: $ROLE" >&2; exit 2;; esac
[[ $(uname -m) == x86_64 ]] || { echo "This pinned lab only supports x86_64" >&2; exit 1; }
umask 077
BASE=/etc/mega-tunnel
D="$BASE/xhttp-$ROLE"
BUNDLE="/root/mega-$ROLE-xhttp-client.json"
STATE="/var/lib/mega-tunnel/xhttp-$ROLE"
LIB=/usr/local/lib/mega-tunnel
BIN="$LIB/xray-v26.9.8"
UNIT="mega-$ROLE-xhttp-foreign.service"
[[ -d "$BASE" && -f "$BASE/stage0.json" ]] || { echo "Run bootstrap-stage0.sh $ROLE first" >&2; exit 1; }
python3 - "$BASE/stage0.json" "$ROLE" <<'PY'
import json,sys
obj=json.load(open(sys.argv[1]))
if obj.get('kind')!='mega-tunnel-stage0' or obj.get('role')!=sys.argv[2]:
 raise SystemExit("Wrong role in stage0 manifest: STOP")
PY
[[ ! -e "$D" && ! -e "$BUNDLE" && ! -e "/etc/systemd/system/$UNIT" ]] ||
 { echo "Prior F2/F4 lab installation exists: STOP, do not overwrite" >&2; exit 1; }
! ss -H -ltn '( sport = :443 )' | grep -q . ||
 { echo "TCP/443 occupied; use dedicated fresh F2/F4 VPS" >&2; exit 1; }
read -r -p "Foreign $ROLE public IPv4: " IP
read -r -p "REALITY camouflage TLS1.3+H2 hostname (e.g. www.microsoft.com): " SNI
export IP SNI
# REALITY target is a remote public TLS site, not a dependency for authorized
# tunnel payload or a CDN carrying client traffic. Validate TLS1.3 + ALPN h2.
python3 - <<'PY'
import ipaddress,os,re,socket,ssl
ip=ipaddress.IPv4Address(os.environ["IP"])
if not ip.is_global: raise SystemExit("Foreign IPv4 is not global")
sni=os.environ["SNI"]
if not re.fullmatch(r'(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}',sni):
 raise SystemExit("Invalid REALITY hostname")
ctx=ssl.create_default_context()
ctx.minimum_version=ssl.TLSVersion.TLSv1_3
ctx.set_alpn_protocols(["h2"])
with socket.create_connection((sni,443),timeout=8) as sock:
 with ctx.wrap_socket(sock,server_hostname=sni) as tls:
  if tls.version()!="TLSv1.3" or tls.selected_alpn_protocol()!="h2":
   raise SystemExit("REALITY target does not support TLSv1.3 + h2; select another")
print("Foreign IPv4 and target TLS1.3/H2: PASS")
PY
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl unzip iproute2 python3
# Xray binary pinned to v26.9.8; official release archive checksum.
ZIPURL='https://github.com/XTLS/Xray-core/releases/download/v26.9.8/Xray-linux-64.zip'
ZIPSHA='a8c6d5b53957600d7e18d16e697201a4c942fe823307deb039bf8f40587aa556'
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
curl -fsSL --retry 3 --connect-timeout 10 --max-time 180 -o "$TMP/xray.zip" "$ZIPURL"
echo "$ZIPSHA  $TMP/xray.zip" | sha256sum -c -
mkdir -p "$TMP/unpack"
unzip -q "$TMP/xray.zip" -d "$TMP/unpack"
[[ -f "$TMP/unpack/xray" ]] || { echo "Verified ZIP has no xray binary" >&2; exit 1; }
install -d -m 0755 "$LIB"
install -m 0755 "$TMP/unpack/xray" "$BIN"
if ! id mega-tunnel >/dev/null 2>&1; then
 useradd --system --no-create-home --shell /usr/sbin/nologin mega-tunnel
fi
[[ $(stat -c %u "$BASE") == 0 ]] || { echo "Unexpected /etc/mega-tunnel ownership" >&2; exit 1; }
chgrp mega-tunnel "$BASE"
chmod 0710 "$BASE"
install -d -o root -g mega-tunnel -m 0750 "$D"
install -d -o mega-tunnel -g mega-tunnel -m 0750 "$STATE"
# Create authenticated REALITY identity and client bundle; no secrets printed.
python3 - "$BIN" "$D/server.json" "$D/pending-bundle.json" "$ROLE" <<'PY'
import hashlib,ipaddress,json,os,re,subprocess,sys,uuid
binary,config,bundle,role=sys.argv[1:]
p=subprocess.run([binary,"x25519"],capture_output=True,text=True,check=True)
key_out=p.stdout
pr=re.search(r'(?im)^Private key:\s*([A-Za-z0-9_-]{43,44})\s*$',key_out)
pub=re.search(r'(?im)^(?:Password|Public key):\s*([A-Za-z0-9_-]{43,44})\s*$',key_out)
if not pr or not pub: raise SystemExit("Xray x25519 output unexpected; do not leak keys")
private,public=pr.group(1),pub.group(1)
uid=str(uuid.uuid4())
shortid=os.urandom(8).hex()
path="/m-"+os.urandom(12).hex()
ip=os.environ["IP"]
sni=os.environ["SNI"]
server={
 "log":{"loglevel":"warning"},
 "inbounds":[{
  "tag":"xhttp-reality-in",
  "listen":"0.0.0.0","port":443,"protocol":"vless",
  "settings":{"clients":[{"id":uid,"flow":""}],"decryption":"none"},
  "streamSettings":{
   "network":"xhttp","xhttpSettings":{"path":path,"mode":"stream-one"},
   "security":"reality",
   "realitySettings":{"show":False,"target":sni+":443",
     "serverNames":[sni],"privateKey":private,"shortIds":[shortid]}}
 }],
 "outbounds":[{"tag":"direct","protocol":"freedom"},
              {"tag":"block","protocol":"blackhole"}],
 "routing":{"domainStrategy":"AsIs",
  "rules":[{"type":"field","inboundTag":["xhttp-reality-in"],
            "network":"udp","outboundTag":"block"}]}
}
manifest={
 "kind":"mega-xhttp-reality-lab","version":1,"foreign_id":role.upper(),
 "public_ip":ip,"port":443,"reality_server_name":sni,"public_key":public,
 "short_id":shortid,"uuid":uid,"xhttp_path":path,
 "xray_binary_sha256":hashlib.sha256(open(binary,"rb").read()).hexdigest(),
 "xray_release":"v26.9.8",
 "transport":"tcp-xhttp-stream-one-reality"
}
for filename,obj in [(config,server),(bundle,manifest)]:
 flags=os.O_CREAT|os.O_EXCL|os.O_WRONLY
 fd=os.open(filename,flags,0o640)
 with os.fdopen(fd,"w") as w: json.dump(obj,w,indent=2)
PY
chown root:mega-tunnel "$D/server.json"
chmod 0640 "$D/server.json"
chmod 0600 "$D/pending-bundle.json"
runuser -u mega-tunnel -- test -r "$D/server.json" ||
 { echo "Restricted user cannot read Xray server config" >&2; exit 1; }
"$BIN" run -test -c "$D/server.json" >/dev/null ||
 { echo "Xray version/config unsupported: STOP" >&2; exit 1; }
cat > "/etc/systemd/system/$UNIT" <<EOF
[Unit]
Description=Mega Tunnel lab REALITY XHTTP TCP $ROLE foreign
Wants=network-online.target
After=network-online.target
[Service]
Type=simple
User=mega-tunnel
Group=mega-tunnel
ExecStart=$BIN run -c $D/server.json
Restart=on-failure
RestartSec=3
MemoryHigh=200M
MemoryMax=420M
LimitNOFILE=65536
NoNewPrivileges=true
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
[Install]
WantedBy=multi-user.target
EOF
systemd-analyze verify "/etc/systemd/system/$UNIT" >/dev/null
systemctl daemon-reload
systemctl enable --now "$UNIT"
for i in $(seq 1 12); do
 if systemctl is-active --quiet "$UNIT" && ss -H -ltn '( sport = :443 )' | grep -q .; then
  break
 fi
 sleep 1
done
systemctl is-active --quiet "$UNIT" || { echo "XHTTP REALITY foreign failed, check its unit" >&2; exit 1; }
ss -H -ltn '( sport = :443 )' | grep -q . ||
 { echo "Foreign :443 listener absent" >&2; exit 1; }
install -m 0600 "$D/pending-bundle.json" "$BUNDLE"
rm -f "$D/pending-bundle.json"
echo "SUCCESS: $ROLE Xray v26.9.8 TCP XHTTP+REALITY foreign is listening on 443."
echo "Private bundle: $BUNDLE (never paste or commit)"
echo "Verified binary for secure copy: $BIN"
echo "Stage2 still needs Iran-side TCP end-to-end test. Do NOT route x-ui users yet."
