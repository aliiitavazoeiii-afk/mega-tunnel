#!/usr/bin/env bash
# Mega Tunnel P1 Naive HTTPS TCP lab on a fresh foreign F1/F3.
# x-ui, Iran routing, UDP and production controller are intentionally untouched.
set -Eeuo pipefail
[[ $(id -u) -eq 0 ]] || { echo "root required" >&2; exit 2; }
umask 077
ROLE="$1"
case "$ROLE" in f1|f3) ;; *) echo "Usage: sudo bash ops/install-naive-lab-foreign.sh f1|f3" >&2; exit 2;; esac
D="/etc/mega-tunnel/naive-$ROLE"
STATE="/var/lib/mega-tunnel/naive-$ROLE"
BIN="/usr/local/lib/mega-tunnel"
BUNDLE="/root/mega-$ROLE-naive-client.json"
SERVICE="mega-$ROLE-naive-foreign"
[[ ! -e "$D" && ! -e "$BUNDLE" ]] || { echo "Existing state found; refusing destructive reinstall" >&2; exit 1; }
if ss -H -ltn 'sport = :443' | grep -q .; then
 echo "TCP/443 already in use; need a fresh dedicated foreign" >&2; exit 1
fi
read -r -p 'New foreign public IPv4: ' IP
read -r -p 'DNS-only hostname pointing to that IP: ' DOMAIN
read -r -p "Let's Encrypt contact email: " EMAIL
export IP DOMAIN EMAIL
python3 - <<'PY'
import ipaddress,os,re,socket
ip=ipaddress.IPv4Address(os.environ['IP'])
if not ip.is_global: raise SystemExit("Foreign must have global public IPv4")
domain=os.environ["DOMAIN"]
if not re.fullmatch(r'(?=.{4,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}',domain):
 raise SystemExit("Invalid DNS hostname")
if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',os.environ["EMAIL"]):
 raise SystemExit("Invalid email")
ips={a[4][0] for a in socket.getaddrinfo(domain,None,family=socket.AF_INET)}
if str(ip) not in ips: raise SystemExit("DNS record must point to foreign public IPv4")
print("Foreign DNS and input checks PASS")
PY
[[ $(uname -m) == x86_64 ]] || { echo "Pinned Caddy build is qualified for x86_64 only" >&2; exit 1; }
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl xz-utils tar openssl iproute2
URL='https://github.com/klzgrad/forwardproxy/releases/download/v2.11.7-naive2/caddy-forwardproxy-naive.tar.xz'
SHA='c273dc07dd79c5919f97639cbdcb559d40ce90475dbd8aac80641b0a8c8065ff'
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
curl -fL --retry 3 --connect-timeout 10 --max-time 180 -o "$TMP/caddy.tar.xz" "$URL"
echo "$SHA  $TMP/caddy.tar.xz" | sha256sum -c -
mkdir -p "$TMP/unpack"
tar -xJf "$TMP/caddy.tar.xz" -C "$TMP/unpack"
FILE=$(find "$TMP/unpack" -type f -name caddy -perm /111 | head -n1)
[[ -n "$FILE" ]] || { echo "Caddy not in verified archive" >&2; exit 1; }
install -d -m 0755 "$BIN"
install -m 0755 "$FILE" "$BIN/caddy-naive-v2.11.7"
if ! id mega-tunnel >/dev/null 2>&1; then
 useradd --system --no-create-home --shell /usr/sbin/nologin mega-tunnel
fi
install -d -o root -g mega-tunnel -m 0750 "$D"
install -d -o mega-tunnel -g mega-tunnel -m 0750 "$STATE" "$STATE/data" "$STATE/config"
PASS=$(openssl rand -hex 32)
NAME="meg-$ROLE-$(openssl rand -hex 4)"
cat > "$D/Caddyfile" <<EOF
{
  order forward_proxy before file_server
}
$DOMAIN {
  tls $EMAIL
  forward_proxy {
    basic_auth $NAME $PASS
    hide_ip
    hide_via
  }
  respond "Service ready" 200
}
EOF
chown root:mega-tunnel "$D/Caddyfile"
chmod 0640 "$D/Caddyfile"
"$BIN/caddy-naive-v2.11.7" validate --config "$D/Caddyfile" --adapter caddyfile >/dev/null
cat > "/etc/systemd/system/$SERVICE.service" <<EOF
[Unit]
Description=Mega Tunnel Naive HTTPS TCP foreign $ROLE (LAB)
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User=mega-tunnel
Group=mega-tunnel
ExecStart=$BIN/caddy-naive-v2.11.7 run --config $D/Caddyfile --adapter caddyfile
Restart=on-failure
RestartSec=3
LimitNOFILE=65536
NoNewPrivileges=true
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$STATE
Environment=HOME=$STATE
Environment=XDG_DATA_HOME=$STATE/data
Environment=XDG_CONFIG_HOME=$STATE/config
PrivateTmp=true
[Install]
WantedBy=multi-user.target
EOF
systemd-analyze verify "/etc/systemd/system/$SERVICE.service"
systemctl daemon-reload
systemctl enable --now "$SERVICE"
READY=0
for i in $(seq 1 35); do
 if curl -4 -sS --connect-timeout 4 --max-time 8 \
  --resolve "$DOMAIN:443:127.0.0.1" -o /dev/null "https://$DOMAIN/"; then
   READY=1; break
 fi
 systemctl is-active --quiet "$SERVICE" || break
 sleep 2
done
if (( READY != 1 )); then
 echo "TLS not ready; inspect journalctl -u $SERVICE" >&2
 exit 1
fi
export PASS NAME
python3 - "$BUNDLE" "$ROLE" <<'PY'
import json,os,sys
path,role=sys.argv[1:]
obj={"version":1,"kind":"mega-naive-lab","foreign_id":role.upper(),
 "public_ip":os.environ["IP"],"domain":os.environ["DOMAIN"],"port":443,
 "username":os.environ["NAME"],"password":os.environ["PASS"]}
fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,"w") as f: json.dump(obj,f,indent=2)
PY
unset PASS
echo "SUCCESS: $ROLE TCP Naive HTTPS foreign operational"
echo "Private bundle: $BUNDLE (do NOT paste into chat)"
echo "Provider firewall: allow inbound TCP 443 and 80 if ACME challenge requires it"
