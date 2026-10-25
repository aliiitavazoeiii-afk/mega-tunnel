#!/usr/bin/env python3
"""Read-only x-ui 2.9.4 runtime/DB readiness inspection after Maya1 rebuild.

Output: only aggregate counts and protocol/transport type categories, no UUIDs,
emails, client IPs, domains, secrets, paths, tokens, passwords or inbound tags.
No DB writes, process restarts, service probes, network changes, or x-ui edits.
"""
import argparse
import json
import re
import sqlite3
import subprocess
from pathlib import Path

VERSION = re.compile(r"(?<!\d)2\.9\.4(?!\d)")
ALLOWED_PROTOCOLS = {"vless", "vmess", "trojan", "shadowsocks", "http", "socks",
                     "mixed", "hysteria", "hysteria2", "wireguard", "tunnel"}
ALLOWED_NETWORKS = {"tcp", "ws", "grpc", "httpupgrade", "xhttp", "kcp", "quic", "h2"}
ALLOWED_SECURITY = {"reality", "tls", "none"}


def _enum(value, permitted):
    return value if value in permitted else "other_or_missing"


def _run(args):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=8)
        if p.returncode:
            return None
        return p.stdout
    except (OSError, subprocess.TimeoutExpired):
        return None


def _port_listeners():
    out = _run(["ss", "-H", "-ltnp"])
    if out is None:
        return None
    ports = {443, 62789, 11111, 2095, 2096}
    result = {str(n): False for n in ports}
    for line in out.splitlines():
        cols = line.split()
        if len(cols) < 5:
            continue
        local = cols[3]
        m = re.search(r":([0-9]{1,5})$", local)
        if not m:
            continue
        port = int(m.group(1))
        if port in ports:
            result[str(port)] = True
    return result


def inspect(db_path, xui_bin, *, version_text=None, listeners=None):
    out = {
        "mode": "READ_ONLY_XUI_294_RUNTIME_AUDIT",
        "version_exact_2_9_4": False,
        "database_readable": False,
        "template_source": "unknown",
        "enabled_inbounds": 0,
        "total_inbounds": 0,
        "public_443_inbounds": 0,
        "protocols": {},
        "networks": {},
        "security_modes": {},
        "clients_in_inbound_json": 0,
        "clients_manually_enabled_in_json": 0,
        "clients_manually_disabled_in_json": 0,
        "clients_without_explicit_enable_flag": 0,
        "client_traffic_rows": None,
        "client_traffic_enabled": None,
        "listeners": None,
        "safe_to_change_xui": False,
        "notice": "Runtime listener presence is not proof of client logins, live traffic, or successful production routing.",
    }
    version_text = version_text if version_text is not None else _run([str(xui_bin), "-v"])
    if version_text is None or not VERSION.search(version_text):
        out["error"] = "Required x-ui 2.9.4 version was not verified"
        return out
    out["version_exact_2_9_4"] = True
    if listeners is None:
        listeners = _port_listeners()
    out["listeners"] = listeners
    db_path = Path(db_path)
    if not db_path.is_file():
        out["error"] = "x-ui SQLite file not found"
        return out
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5) as conn:
            out["database_readable"] = True
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            if not {"inbounds", "settings"}.issubset(tables):
                out["error"] = "x-ui settings or inbounds table missing"
                return out
            row = conn.execute(
                'SELECT 1 FROM "settings" WHERE "key"=? LIMIT 1',
                ("xrayTemplateConfig",)
            ).fetchone()
            out["template_source"] = ("database_saved" if row else "built_in_default_possible")
            columns = {r[1] for r in conn.execute('PRAGMA table_info("inbounds")')}
            required = {"port", "enable", "protocol", "settings", "stream_settings"}
            # 3x-ui GORM maps StreamSettings to stream_settings, but verify,
            # rather than assume schema after migrations.
            if not required.issubset(columns):
                out["error"] = "Unexpected inbound schema (read-only review required)"
                out["columns_presence"] = {c: c in columns for c in sorted(required)}
                return out
            rows = conn.execute(
                'SELECT "port","enable","protocol","settings","stream_settings" FROM "inbounds"'
            ).fetchall()
            out["total_inbounds"] = len(rows)
            for port, enabled, protocol, settings, stream_settings in rows:
                if int(enabled or 0) != 1:
                    continue
                out["enabled_inbounds"] += 1
                if port == 443:
                    out["public_443_inbounds"] += 1
                p = _enum(protocol, ALLOWED_PROTOCOLS)
                out["protocols"][p] = out["protocols"].get(p, 0) + 1
                try:
                    transport = json.loads(stream_settings or "{}")
                    if not isinstance(transport, dict):
                        transport = {}
                except (ValueError, TypeError):
                    transport = {}
                net = _enum(transport.get("network"), ALLOWED_NETWORKS)
                sec = _enum(transport.get("security"), ALLOWED_SECURITY)
                out["networks"][net] = out["networks"].get(net, 0) + 1
                out["security_modes"][sec] = out["security_modes"].get(sec, 0) + 1
                try:
                    settings_obj = json.loads(settings or "{}")
                    clients = settings_obj.get("clients", []) if isinstance(settings_obj, dict) else []
                    if not isinstance(clients, list):
                        clients = []
                except (ValueError, TypeError):
                    clients = []
                for c in clients:
                    if not isinstance(c, dict):
                        continue
                    out["clients_in_inbound_json"] += 1
                    if c.get("enable") is True:
                        out["clients_manually_enabled_in_json"] += 1
                    elif c.get("enable") is False:
                        out["clients_manually_disabled_in_json"] += 1
                    else:
                        out["clients_without_explicit_enable_flag"] += 1
            if "client_traffics" in tables:
                out["client_traffic_rows"] = conn.execute(
                    'SELECT COUNT(*) FROM "client_traffics"'
                ).fetchone()[0]
                stats_cols = {r[1] for r in conn.execute(
                    'PRAGMA table_info("client_traffics")'
                )}
                if "enable" in stats_cols:
                    out["client_traffic_enabled"] = conn.execute(
                        'SELECT COUNT(*) FROM "client_traffics" WHERE "enable"=1'
                    ).fetchone()[0]
    except (sqlite3.Error, TypeError, ValueError) as e:
        out["error"] = "SQLite inspection error: " + type(e).__name__
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="/etc/x-ui/x-ui.db")
    ap.add_argument("--xui-bin", default="/usr/local/x-ui/x-ui")
    args = ap.parse_args()
    result = inspect(args.db, args.xui_bin)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if "error" in result:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
