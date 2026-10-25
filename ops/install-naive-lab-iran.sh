#!/usr/bin/env bash
# Mega Tunnel Stage-1: live Naive TCP lab from Iran to F1 (or F3).
# Binds local SOCKS only, does not change x-ui, firewall, subscriptions or default route.
set -Eeuo pipefail
[[ $(id -u) -eq 0 ]] || { echo "root required" >&2; exit 2; }
[[ $# -eq 2 ]] || { echo "Usage: sudo bash ops/install-naive-lab-iran.sh maya1|maya3 /root/mega-f1-naive-client.json" >&2; exit 2; }
GATEWAY="$1"
BUNDLE="$2"
case "$GATEWAY" in
 maya1) ROLE=f1; PORT=17995 ;;
 maya3) ROLE=f3; PORT=17997 ;;
 *) echo "Only Maya1/Maya3 currently supported" >&2; exit 2;;
esac
[[ -s "$BUNDLE" ]] || { echo "Bundle file not found (do not paste its contents anywhere)" >&2; exit 2; }
umask 077
D="/etc/mega-tunnel/naive-$ROLE"
BIN="/usr/local/lib/mega-tunnel"
SERVICE="mega-$ROLE-naive-client"
[[ ! -e "$D" ]] || { echo "Existing lab configuration; refusing destructive reinstall" >&2; exit 1; }
if ss -H -ltn "sport = :$PORT" | grep -q .; then
 echo "TCP port $PORT already in use" >&2; exit 1
fi
# A false version match must never result in editing or installing x-ui.
[[ -x /usr/local/x-ui/x-ui ]] || { echo "x-ui must already be installed" >&2; exit 1; }
XV=$(/usr/local/x-ui/x-ui -v 2>/dev/null | tr -d '[:space:]')
XV=$(echo "$XV" | sed 's/^v//')
[[ "$XV" == 2.9.4 ]] || { echo "Expected installed x-ui 2.9.4; found $XV" >&2; exit 1; }
python3 - "$BUNDLE" "$ROLE" <<'PY'
import json,ipaddress,re,sys
b=json.load(open(sys.argv[1]))
role=sys.argv[2]
assert b.get("version")==1 and b.get("kind")=="mega-naive-lab" and b.get("foreign_id")==role.upper(), "Wrong role/bundle"
assert b.get("port")==443
assert ipaddress.IPv4Address(b["public_ip"]).is_global
assert re.fullmatch(r'(?=.{4,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}',b["domain"])
assert re.fullmatch(r'meg-(?:f1|f3)-[a-f0-9]{8}',b["username"])
assert re.fullmatch(r'[a-f0-9]{64}',b["password"])
print("Lab bundle validated:", role)
PY
[[ $(uname -m) == x86_64 ]] || { echo "x64 pinned Naive binary required" >&2; exit 1; }
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl xz-utils tar iproute2
URL='https://github.com/klzgrad/naiveproxy/releases/download/v154.0.8037.49-5/naiveproxy-v154.0.8037.49-5-linux-x64.tar.xz'
SHA='80214dfea1767f6ecf63a3a79dc9f48b203460f51abc609357fff48dd5844c7d'
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
curl -fL --retry 3 --connect-timeout 10 --max-time 180 -o "$TMP/naive.tar.xz" "$URL"
echo "$SHA  $TMP/naive.tar.xz" | sha256sum -c -
mkdir -p "$TMP/unpack"
tar -xJf "$TMP/naive.tar.xz" -C "$TMP/unpack"
FILE=$(find "$TMP/unpack" -type f -name naive -perm /111 | head -n1)
[[ -n "$FILE" ]] || { echo "naive executable missing" >&2; exit 1; }
install -d -m 0755 "$BIN"
install -m 0755 "$FILE" "$BIN/naive-v154"
if ! id mega-tunnel >/dev/null 2>&1; then
 useradd --system --no-create-home --shell /usr/sbin/nologin mega-tunnel
fi
# Stage0 sets the root parent to 0700, so the unprivileged Naive process
# needs group execute-only access to traverse to its private configuration.
# Group read is NOT granted on the shared root parent or its other secrets.
[[ -d /etc/mega-tunnel && $(stat -c %u /etc/mega-tunnel) == 0 ]] ||
 { echo "Unexpected /etc/mega-tunnel ownership; abort" >&2; exit 1; }
chgrp mega-tunnel /etc/mega-tunnel
chmod 0710 /etc/mega-tunnel
install -d -o root -g mega-tunnel -m 0750 "$D"
python3 - "$BUNDLE" "$D/client.json" "$PORT" <<'PY'
import json,os,sys
bundle_path,config_path,port=sys.argv[1:]
with open(bundle_path) as f: b=json.load(f)
c={
 "listen":f"socks://127.0.0.1:{port}",
 "proxy":f"https://{b['username']}:{b['password']}@{b['domain']}",
 "host-resolver-rules":f"MAP {b['domain']} {b['public_ip']}"
}
fd=os.open(config_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o640)
with os.fdopen(fd,"w") as f: json.dump(c,f,indent=2)
PY
chown root:mega-tunnel "$D/client.json"
runuser -u mega-tunnel -- test -r "$D/client.json" ||
 { echo "Naive system user cannot read its config; aborting before start" >&2; exit 1; }
cat > "/etc/systemd/system/$SERVICE.service" <<EOF
[Unit]
Description=Mega Tunnel Naive TCP lab $GATEWAY -> $ROLE
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User=mega-tunnel
Group=mega-tunnel
ExecStart=$BIN/naive-v154 $D/client.json
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
systemd-analyze verify "/etc/systemd/system/$SERVICE.service"
systemctl daemon-reload
systemctl enable --now "$SERVICE"
echo "=== Naive TCP lab path test: localhost:$PORT ==="
GOOD=0
for i in 1 2 3 4 5; do
 CODE=$(curl -4 -sS --socks5-hostname "127.0.0.1:$PORT" \
   --connect-timeout 6 --max-time 15 -o /dev/null -w '%{http_code}' \
   https://www.gstatic.com/generate_204 2>/dev/null || true)
 echo "test $i / 5: HTTP $CODE"
 if [[ "$CODE" == 204 ]]; then GOOD=$((GOOD+1)); fi
 sleep 1
done
echo "Passed requests: $GOOD/5"
if (( GOOD < 4 )); then
 echo "NOT READY: inspect systemctl status $SERVICE and journalctl -u $SERVICE" >&2
 exit 1
fi
echo "SUCCESS: real encrypted Naive TCP lab path. No x-ui changes."
echo "Use: sudo bash ops/test-naive-lab.sh $GATEWAY"
