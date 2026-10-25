#!/usr/bin/env python3
"""Maya1 x-ui 2.9.4 -> Mega Router 17990 adapter with protected rollback.

This is an explicit, operator-triggered LIVE Xray routing change.
Never changes inbound user UUID/REALITY/private keys/subscription settings,
foreign services, firewall or machine routes. DOES restart x-ui once.
Roll back via: sudo python3 ops/connect-xui-to-mega.py rollback
"""
import fcntl
import hashlib
import json
import os
import re
import socket
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

DB = Path("/etc/x-ui/x-ui.db")
XUI = Path("/usr/local/x-ui/x-ui")
VENDOR = Path(__file__).resolve().parent / "vendor/3x-ui-v2.9.4-default-xray.json"
STATEDIR = Path("/var/lib/mega-tunnel")
STATEFILE = STATEDIR / "maya1-xui-router-rollback.json"
BACKUPDIR = Path("/var/backups/mega-tunnel")
TAG = "mega-router"
PORT = 17990


def fail(message):
    raise RuntimeError(message)


def run(argv, *, timeout=20, quiet=False):
    p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    if p.returncode:
        # NEVER print raw stdout/stderr for config-bearing commands.
        fail("command failed: " + argv[0] + " " + (argv[1] if len(argv) > 1 else ""))
    return p.stdout if not quiet else ""


def is_active(unit):
    return subprocess.run(["systemctl", "is-active", "--quiet", unit]).returncode == 0


def listens_local(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except OSError:
        return False


def listens_443():
    # TCP socket can be dual-stack; inspect kernel's listening sockets via ss.
    p = subprocess.run(["ss", "-H", "-ltn", "( sport = :443 )"],
                       capture_output=True, text=True, timeout=5)
    return p.returncode == 0 and bool(p.stdout.strip())


def db_connect():
    conn = sqlite3.connect(f"file:{DB}?mode=rw", uri=True, timeout=10)
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def read_setting(conn):
    return conn.execute(
        'SELECT "value" FROM "settings" WHERE "key"=? LIMIT 1',
        ("xrayTemplateConfig",)
    ).fetchone()


def set_template(value):
    with db_connect() as conn:
        row = read_setting(conn)
        if row is None:
            conn.execute('INSERT INTO "settings" ("key","value") VALUES (?,?)',
                         ("xrayTemplateConfig", value))
        else:
            conn.execute('UPDATE "settings" SET "value"=? WHERE "key"=?',
                         (value, "xrayTemplateConfig"))


def delete_template():
    with db_connect() as conn:
        conn.execute('DELETE FROM "settings" WHERE "key"=?',
                     ("xrayTemplateConfig",))


def digest(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def protected_state(data):
    STATEDIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(STATEDIR, 0o700)
    fd, temp = tempfile.mkstemp(prefix=".xui-rollback-", dir=STATEDIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, STATEFILE)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def vendor_template():
    cfg = json.loads(VENDOR.read_text(encoding="utf-8"))
    if (cfg.get("api", {}).get("tag") != "api" or
        cfg.get("inbounds", [{}])[0].get("port") != 62789 or
        cfg.get("outbounds", [{}])[0].get("tag") != "direct" or
        cfg.get("metrics", {}).get("listen") != "127.0.0.1:11111"):
        fail("pinned 3x-ui v2.9.4 default differs; STOP")
    return cfg


def load_inbound(conn):
    cols = {r[1] for r in conn.execute('PRAGMA table_info("inbounds")')}
    expected = {"port", "enable", "protocol", "settings",
                "stream_settings", "tag", "listen", "sniffing"}
    if not expected.issubset(cols):
        fail("inbound schema differs from verified x-ui 2.9.4")
    rows = conn.execute(
        'SELECT "port","enable","protocol","settings",'
        '"stream_settings","tag","listen","sniffing" FROM "inbounds"'
    ).fetchall()
    enabled = [r for r in rows if int(r[1] or 0) == 1]
    if len(rows) != 1 or len(enabled) != 1:
        fail("Expected exactly one enabled x-ui inbound (other setups need review)")
    port, _, protocol, settings, stream, tag, listen, sniffing = enabled[0]
    if port != 443 or protocol != "vless" or not isinstance(tag, str) or not tag:
        fail("Expected one VLESS inbound on TCP/443 with an existing tag")
    if tag in ("api", TAG):
        fail("Inbound tag conflicts with reserved adapter tag")
    streamcfg = json.loads(stream)
    settingscfg = json.loads(settings)
    if not isinstance(streamcfg, dict) or not isinstance(settingscfg, dict):
        fail("Malformed inbound JSON")
    if streamcfg.get("network") not in ("tcp", "raw") or streamcfg.get("security") != "reality":
        fail("Expected existing TCP + REALITY inbound")
    clients = settingscfg.get("clients", [])
    if not isinstance(clients, list) or len(clients) < 1:
        fail("No clients found in existing inbound; STOP")
    return (enabled[0], str(tag), len(clients))


def build_candidate(base, inbound_tag):
    cfg = json.loads(json.dumps(base))
    outs = cfg.get("outbounds")
    routing = cfg.get("routing")
    if not isinstance(outs, list) or not isinstance(routing, dict):
        fail("Malformed Xray template")
    rules = routing.get("rules")
    if not isinstance(rules, list):
        fail("Missing Xray routing rules")
    tags = [o.get("tag") for o in outs if isinstance(o, dict)]
    if TAG in tags:
        fail("Router outbound tag already exists; manual review required")
    if any(TAG == r.get("outboundTag") for r in rules if isinstance(r, dict)):
        fail("Router routing already exists; manual review required")
    if not any("api" in r.get("inboundTag", []) and r.get("outboundTag") == "api"
               for r in rules if isinstance(r, dict)):
        fail("Original x-ui API routing rule missing")
    # SOCKS protocol settings require a single server under servers[].
    # The original top-level {"address","port"} example is invalid here.
    outs.append({
        "tag": TAG,
        "protocol": "socks",
        "settings": {"servers": [{"address": "127.0.0.1", "port": PORT}]}
    })
    # Existing API and security deny rules retain their precedence.
    rules.append({
        "type": "field", "inboundTag": [inbound_tag],
        "network": "tcp", "outboundTag": TAG
    })
    # UDP can't safely pass a TCP-only upstream; refuse rather than leak direct.
    rules.append({
        "type": "field", "inboundTag": [inbound_tag],
        "network": "udp", "outboundTag": "blocked"
    })
    return cfg


def candidate_xray_config(template, inbound):
    port, _, protocol, settings, stream, tag, listen, sniffing = inbound
    incfg = json.loads(settings)
    raw_stream = json.loads(stream)
    if isinstance(raw_stream.get("tlsSettings"), dict):
        raw_stream["tlsSettings"].pop("settings", None)
    if isinstance(raw_stream.get("realitySettings"), dict):
        raw_stream["realitySettings"].pop("settings", None)
    raw_stream.pop("externalProxy", None)
    clients = incfg.get("clients")
    if isinstance(clients, list):
        filtered = []
        for original in clients:
            if not isinstance(original, dict) or original.get("enable") is False:
                continue
            clean = {k: v for k, v in original.items() if
                     k in ("email", "id", "password", "flow", "method",
                           "auth", "reverse")}
            if clean.get("flow") == "xtls-rprx-vision-udp443":
                clean["flow"] = "xtls-rprx-vision"
            filtered.append(clean)
        incfg["clients"] = filtered
    # This is ONLY a parse validation, and is NOT written to x-ui.
    merged = json.loads(json.dumps(template))
    merged.setdefault("inbounds", []).append({
        "tag": tag, "listen": listen or "0.0.0.0", "port": port,
        "protocol": protocol, "settings": incfg,
        "streamSettings": raw_stream,
        "sniffing": json.loads(sniffing) if sniffing else {},
    })
    return merged


def xray_binary_for_port_443():
    p = subprocess.run(
        ["ss", "-H", "-ltnp", "( sport = :443 )"],
        capture_output=True, text=True, timeout=5
    )
    if p.returncode:
        fail("Cannot inspect existing 443 listener")
    for pid in re.findall(r"pid=(\d+)", p.stdout):
        exe = Path(f"/proc/{pid}/exe")
        try:
            resolved = os.readlink(exe)
        except OSError:
            continue
        if "xray" in Path(resolved).name.lower():
            return exe
    fail("Cannot identify existing Xray core binary on 443")


def xray_parse_test(template, inbound):
    config = candidate_xray_config(template, inbound)
    with tempfile.TemporaryDirectory(prefix="mega-xui-validate-") as temp:
        p = Path(temp)
        os.chmod(p, 0o700)
        cf = p / "candidate.json"
        fd = os.open(cf, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(config, f)
        exe = xray_binary_for_port_443()
        # Fail closed on parser/version failure; never print secrets or raw logs.
        p = subprocess.run([str(exe), "run", "-test", "-c", str(cf)],
                           capture_output=True, text=True, timeout=20)
        if p.returncode:
            fail("Existing Xray core rejected generated candidate config; "
                 "nothing was applied. Needs compatibility review.")


def restart_and_validate():
    p = subprocess.run(["systemctl", "restart", "x-ui.service"],
                       capture_output=True, text=True, timeout=35)
    if p.returncode:
        return False
    for _ in range(25):
        if (is_active("x-ui.service") and listens_443() and
                listens_local(62789) and is_active("mega-maya1-router-lab.service")):
            return True
        time.sleep(1)
    return False


def run_rollback(*, automatic=False):
    if not STATEFILE.is_file():
        fail("No saved routing change found to roll back")
    data = json.loads(STATEFILE.read_text(encoding="utf-8"))
    if data.get("database_path") != str(DB):
        fail("Rollback DB identity mismatch")
    backup = Path(data["backup"])
    if not backup.is_file():
        fail("Protected x-ui DB backup missing; no mutation done")
    with sqlite3.connect(f"file:{backup}?mode=ro", uri=True) as con:
        prev = read_setting(con)
    with db_connect() as con:
        current = read_setting(con)
    if (current is not None and digest(current[0]) != data["candidate_sha256"]
            and not automatic):
        fail("Template was changed after adapter install; refusing to overwrite")
    if prev is None:
        delete_template()
    else:
        set_template(prev[0])
    if not restart_and_validate():
        fail("Old template restored, but x-ui 443 or API listener failed after restart. "
             "Check x-ui service independently.")
    STATEFILE.unlink()
    print("ROLLBACK OK: restored original x-ui template setting only; "
          "all original users and foreign carrier services unchanged.", flush=True)


def preflight():
    if os.geteuid() != 0:
        fail("Run with sudo/root")
    version = run([str(XUI), "-v"], timeout=9)
    if not re.search(r"(?<!\d)2\.9\.4(?!\d)", version):
        fail("x-ui is not exactly v2.9.4")
    if not DB.is_file():
        fail("x-ui database missing")
    if STATEFILE.exists():
        fail("An earlier adapter deployment has rollback state. "
             "Use rollback or inspect state before another apply.")
    for unit in ("x-ui.service", "mega-f1-naive-client.service",
                 "mega-f2-xhttp-client.service", "mega-maya1-router-lab.service"):
        if not is_active(unit):
            fail("Service is not active: " + unit)
    if not listens_443() or not listens_local(PORT):
        fail("x-ui 443 or local Mega Router 17990 is not listening")
    # One small real request proves this exact SOCKS data plane currently works.
    p = subprocess.run(
        ["curl", "-4", "--noproxy", "", "--proxy",
         "socks5h://127.0.0.1:17990", "-sS", "--connect-timeout", "7",
         "--max-time", "15", "-o", "/dev/null", "-w", "%{http_code}",
         "https://www.gstatic.com/generate_204"],
        capture_output=True, text=True, timeout=18
    )
    if p.returncode or p.stdout.strip() != "204":
        fail("Mega Router live HTTPS 204 check failed; no x-ui changes made")


def backup_database():
    BACKUPDIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(BACKUPDIR, 0o700)
    fd, file = tempfile.mkstemp(prefix="maya1-xui294-pre-mega-",
                                suffix=".sqlite", dir=BACKUPDIR)
    os.close(fd)
    os.chmod(file, 0o600)
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10) as src:
        with sqlite3.connect(file) as dst:
            src.backup(dst)
    return file


def apply():
    preflight()
    base = vendor_template()
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10) as con:
        inbound, inbound_tag, count = load_inbound(con)
        original = read_setting(con)
    if original is not None:
        # Preserving an unknown custom template cannot be inferred from
        # the bundled upstream default. STOP rather than overwrite it.
        fail("Custom xrayTemplateConfig saved in DB; automatic adapter refuses "
             "to replace it. Nothing changed.")
    candidate = build_candidate(base, inbound_tag)
    xray_parse_test(candidate, inbound)
    print(f"PRECHECK OK: 1 TCP/REALITY inbound :443, {count} saved clients, "
          "F1/F2 and 17990 healthy, Xray parser PASS", flush=True)
    backup = backup_database()
    value = json.dumps(candidate, ensure_ascii=False, separators=(",", ":"))
    protected_state({
        "database_path": str(DB),
        "backup": backup,
        "candidate_sha256": digest(value),
        "created_at_unix": int(time.time()),
        "source": "upstream_3xui_2_9_4_bundled_default",
    })
    try:
        set_template(value)
        if not restart_and_validate():
            fail("Xray or x-ui did not reopen public :443/API after applying routing")
    except BaseException:
        print("Apply failed; attempting automatic template-only rollback...",
              file=sys.stderr, flush=True)
        run_rollback(automatic=True)
        raise
    print("ROUTING APPLIED: x-ui VLESS/REALITY :443 TCP -> "
          "SOCKS 127.0.0.1:17990 -> F1/F2.", flush=True)
    print("UUIDs, inbound keys and existing user profiles were NOT edited.")
    print("UDP from this inbound is blocked (TCP-only link; no direct leak).")
    print("TRY ONE EXISTING VPN USER NOW. If it fails, run:", flush=True)
    print("  sudo python3 ops/connect-xui-to-mega.py rollback", flush=True)
    print("Note: public ingress TLS/REALITY, domain/IP reachability and actual "
          "client login have not been tested by this server-side change.")


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("apply", "rollback"):
        raise SystemExit(
            "Usage: sudo python3 ops/connect-xui-to-mega.py apply|rollback"
        )
    os.umask(0o077)
    if os.geteuid() != 0:
        raise SystemExit("root required")
    with open("/run/mega-xui-egress-adapter.lock", "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            if sys.argv[1] == "apply":
                apply()
            else:
                run_rollback()
        except (OSError, ValueError, TypeError, KeyError,
                RuntimeError, sqlite3.Error, subprocess.TimeoutExpired) as err:
            print("STOP: " + str(err), file=sys.stderr, flush=True)
            raise SystemExit(1) from None


if __name__ == "__main__":
    main()
