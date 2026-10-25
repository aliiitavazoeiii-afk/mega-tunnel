#!/usr/bin/env bash
# Mega Tunnel stage 0: minimal role inventory and preflight, NO tunnel wiring.
set -Eeuo pipefail
[[ $(id -u) -eq 0 ]] || { echo "Run as root." >&2; exit 1; }
[[ $# -eq 1 ]] || { echo "Usage: sudo bash ops/bootstrap-stage0.sh maya1|maya3|f1|f2|f3|f4" >&2; exit 2; }
ROLE="$1"
case "$ROLE" in
 maya1|maya3|f1|f2|f3|f4) ;;
 *) echo "Invalid role: $ROLE" >&2; exit 2 ;;
esac
umask 077
BASE=/etc/mega-tunnel
DATA=/var/lib/mega-tunnel
echo "=== MEGA TUNNEL STAGE 0 :: $ROLE ==="
echo "No VPN services or client routes will be changed."
# Create missing directories once; never reset permissions on an existing
# lab installation. F1/F2 use group execute-only access to the stage0 parent,
# and re-running preflight must not make running clients unable to read configs.
for dir in "$BASE" "$DATA" "$DATA/backups"; do
 if [[ ! -e "$dir" ]]; then install -d -m 0700 "$dir"; fi
 [[ -d "$dir" && ! -L "$dir" && $(stat -c %u "$dir") == 0 ]] ||
   { echo "Unexpected stage0 directory type/owner: $dir" >&2; exit 1; }
done
python3 - "$BASE/stage0.json" "$ROLE" <<'PY'
import json,os,sys,tempfile
p,role=sys.argv[1:]
if os.path.exists(p):
    with open(p,encoding="utf-8") as f: current=json.load(f)
    if current.get("role") != role:
        raise SystemExit("STOP: a different role already bootstrapped on this host")
    print("Existing role retained:",role)
else:
    d=os.path.dirname(p)
    fd,tmp=tempfile.mkstemp(prefix=".stage0-",dir=d)
    try:
        os.chmod(tmp,0o600)
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            json.dump({"kind":"mega-tunnel-stage0","role":role,
                       "production_transport_installed":False,
                       "user_routing_modified":False},f,indent=2)
            f.write("\n")
        os.replace(tmp,p)
    except BaseException:
        if os.path.exists(tmp): os.unlink(tmp)
        raise
    print("Role manifest created:",role)
PY
DIR=$(cd -- "$(dirname -- "$0")" && pwd)
if [[ "$ROLE" == maya1 || "$ROLE" == maya3 ]]; then
 bash "$DIR/preflight-iran.sh"
 if [[ -x /usr/local/x-ui/x-ui ]]; then
   if python3 "$DIR/audit-xui294.py"; then
      echo "x-ui 2.9.4 schema audit: PASS"
   else
      echo "x-ui schema audit: NOT PASSED — manual review required"
   fi
 else
   echo "x-ui not installed; stage 0 does not install a panel."
 fi
else
 bash "$DIR/preflight-foreign.sh"
fi
echo "=== STAGE 0 COMPLETE ==="
echo "No NaiveProxy/XHTTP, controller or x-ui integration has been deployed."
echo "No services stopped or restarted."
