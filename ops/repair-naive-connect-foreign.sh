#!/usr/bin/env bash
# Repair existing F1/F3 Caddy site address so forward_proxy can receive
# CONNECT requests whose authority is the TARGET, not the proxy hostname.
# Does not change proxy credentials, x-ui, firewall or client config.
set -Eeuo pipefail
[[ $(id -u) -eq 0 ]] || { echo "root required" >&2; exit 2; }
[[ $# -eq 1 ]] || { echo "Usage: sudo bash ops/repair-naive-connect-foreign.sh f1|f3" >&2; exit 2; }
ROLE=$1
case "$ROLE" in f1|f3) ;; *) echo "Foreign role must be f1 or f3" >&2; exit 2;; esac
SERVICE="mega-$ROLE-naive-foreign.service"
CONF="/etc/mega-tunnel/naive-$ROLE/Caddyfile"
BIN="/usr/local/lib/mega-tunnel/caddy-naive-v2.11.7"
STAGE="/etc/mega-tunnel/stage0.json"
BKROOT="/var/lib/mega-tunnel/backups"
[[ -f "$CONF" && -x "$BIN" && -f "$STAGE" ]] || { echo "Foreign setup missing; STOP" >&2; exit 1; }
python3 - "$STAGE" "$ROLE" <<'PY'
import json,sys
s=json.load(open(sys.argv[1]))
if s.get("kind")!="mega-tunnel-stage0" or s.get("role")!=sys.argv[2]:
    raise SystemExit("This host's stage0 role does not match")
PY
# Site must be exactly one FQDN block from the original pinned F1 installer,
# or the same block already preceded by :443. Never try modifying arbitrary Caddyfiles.
read -r DOMAIN CURRENT_STATE < <(python3 - "$CONF" <<'PY'
import pathlib,re,sys
s=pathlib.Path(sys.argv[1]).read_text()
bare=re.findall(r'(?m)^([A-Za-z0-9.-]+\.[A-Za-z]{2,})\s*\{\s*$',s)
both=re.findall(r'(?m)^:443,\s+([A-Za-z0-9.-]+\.[A-Za-z]{2,})\s*\{\s*$',s)
if len(bare)+len(both)!=1:
    raise SystemExit("Caddy has ambiguous site blocks, STOP")
if s.count("forward_proxy {")!=1 or s.count("basic_auth ")!=1:
    raise SystemExit("Unexpected proxy config shape, STOP")
domain=(bare+both)[0]
print(domain, "patched" if both else "unpatched")
PY
)
[[ -n "$DOMAIN" && -n "$CURRENT_STATE" ]] || { echo "Unable to parse Caddy hostname; STOP" >&2; exit 1; }
CHANGED=0
DONE=0
BACKUP=''
rollback(){
 rc=$?
 trap - EXIT
 if (( rc != 0 && CHANGED == 1 && DONE == 0 )); then
  echo "REPAIR FAILED: restoring original Caddyfile and restarting only $SERVICE" >&2
  cp -p "$BACKUP" "$CONF" || true
  systemctl restart "$SERVICE" >/dev/null 2>&1 || true
 fi
 exit "$rc"
}
trap rollback EXIT
if [[ "$CURRENT_STATE" == 'unpatched' ]]; then
 install -d -o root -g root -m 0700 "$BKROOT"
 BACKUP="$BKROOT/$ROLE-caddy-$(date -u +%Y%m%dT%H%M%SZ)-$$.bak"
 cp -p "$CONF" "$BACKUP"
 chmod 0600 "$BACKUP"
 python3 - "$CONF" "$DOMAIN" <<'PY'
import os,pathlib,re,sys,tempfile
p=pathlib.Path(sys.argv[1]); domain=sys.argv[2]
s=p.read_text()
pattern=r'(?m)^'+re.escape(domain)+r'(?=\s*\{\s*$)'
out,n=re.subn(pattern,':443, '+domain,s)
if n!=1: raise SystemExit("Refusing ambiguous site patch")
stat=p.stat()
fd,tmp=tempfile.mkstemp(dir=p.parent,prefix=".Caddyfile-f1-connect-")
try:
 os.fchown(fd,stat.st_uid,stat.st_gid)
 os.fchmod(fd,stat.st_mode & 0o777)
 with os.fdopen(fd,'w') as f:
  f.write(out)
  f.flush(); os.fsync(f.fileno())
 os.replace(tmp,p)
except BaseException:
 try: os.unlink(tmp)
 except FileNotFoundError: pass
 raise
PY
 CHANGED=1
 echo "Caddy site router repaired: :443, $DOMAIN (credentials unchanged)"
 "$BIN" validate --config "$CONF" --adapter caddyfile >/dev/null
 systemctl restart "$SERVICE"
else
 echo "Correct :443 site router already present; not restarting healthy service"
fi
systemctl is-active --quiet "$SERVICE" || { echo "Foreign service not active" >&2; exit 1; }
# Unauthenticated normal HTTPS request must still require proxy credentials.
READY=0
for _ in $(seq 1 15); do
 CODE=$(curl -4 --noproxy '*' -sS --connect-timeout 4 --max-time 8 \
     --resolve "$DOMAIN:443:127.0.0.1" -o /dev/null -w '%{http_code}' \
     "https://$DOMAIN/" 2>/dev/null || true)
 if [[ "$CODE" == 407 ]]; then READY=1; break; fi
 sleep 2
done
(( READY == 1 )) || { echo "Expected TLS-verified 407 auth challenge; observed $CODE" >&2; exit 1; }
echo "Trusted TLS and proxy authentication required: PASS (407)"
# Test HTTP/1.1 authenticated CONNECT over a real TLS connection.
# Credentials are extracted and used ONLY inside this short-lived process.
# No private values or headers are printed or placed on the shell command line.
python3 - "$CONF" "$DOMAIN" <<'PY'
import base64,re,socket,ssl,sys
from pathlib import Path
conf,domain=sys.argv[1:]
s=Path(conf).read_text()
m=re.findall(r'(?m)^\s*basic_auth\s+(\S+)\s+(\S+)\s*$',s)
if len(m)!=1: raise SystemExit("Invalid auth entries")
username,password=m[0]
ctx=ssl.create_default_context()
ctx.set_alpn_protocols(["http/1.1"])
with socket.create_connection(("127.0.0.1",443),timeout=7) as sock:
 with ctx.wrap_socket(sock,server_hostname=domain) as tls:
  tls.settimeout(8)
  auth=base64.b64encode((username+":"+password).encode("utf-8")).decode("ascii")
  request=("CONNECT example.com:443 HTTP/1.1\r\n"
           "Host: example.com:443\r\n"
           "Proxy-Authorization: Basic "+auth+"\r\n"
           "Proxy-Connection: Keep-Alive\r\n\r\n")
  tls.sendall(request.encode("ascii"))
  header=b""
  while b"\r\n\r\n" not in header and len(header)<8192:
   block=tls.recv(1024)
   if not block: break
   header+=block
  line=header.split(b"\r\n",1)[0].decode("ascii","replace")
  result=re.fullmatch(r'HTTP/1\.[01]\s+([0-9]{3})(?:\s+.*)?',line)
  code=result.group(1) if result else "no HTTP response"
  print("Authenticated HTTP/1.1 CONNECT example.com:443 =",code)
  if code!="200":
   raise SystemExit("CONNECT NOT VERIFIED; do not attach users")
PY
DONE=1
echo "SUCCESS: F1/F3 Caddy now accepts authenticated CONNECT requests."
echo "Original Caddy config backup: $BACKUP"
echo "Next test: from Maya1 run sudo bash ops/test-naive-lab.sh maya1"
