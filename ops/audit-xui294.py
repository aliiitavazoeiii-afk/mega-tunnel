#!/usr/bin/env python3
"""Fail-closed read-only x-ui 2.9.4 inspector (no client secrets emitted)."""
import argparse
import json
import re
import sqlite3
import subprocess
from pathlib import Path


def inspect(db_path, xui_bin):
    result = {
        "mode": "READ_ONLY_XUI_294_AUDIT",
        "version_exact_2_9_4": False,
        "database_readable": False,
        "xray_template_valid_json": False,
        "api_routing_rules_present": False,
        "public_443_inbounds": None,
        "client_configuration_unchanged": True,
    }
    binpath = Path(xui_bin)
    if not binpath.is_file():
        result["fatal"] = "x-ui binary unavailable"
        return result
    try:
        process = subprocess.run(
            [str(binpath), "-v"], capture_output=True,
            text=True, timeout=8
        )
        line = process.stdout + process.stderr
        result["version_exact_2_9_4"] = bool(
            re.search(r"(?<!\d)2\.9\.4(?!\d)", line)
        )
    except (OSError, subprocess.TimeoutExpired):
        result["fatal"] = "x-ui version query failed"
        return result
    if not result["version_exact_2_9_4"]:
        result["fatal"] = "x-ui version differs from required 2.9.4"
        return result

    db = Path(db_path)
    if not db.is_file():
        result["fatal"] = "x-ui DB unavailable"
        return result
    try:
        with sqlite3.connect(
            f"file:{db}?mode=ro", uri=True, timeout=5
        ) as conn:
            result["database_readable"] = True
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            if "settings" not in tables or "inbounds" not in tables:
                result["fatal"] = "required x-ui tables missing"
                return result
            row = conn.execute(
                "SELECT value FROM settings WHERE key=?",
                ("xrayTemplateConfig",)
            ).fetchone()
            if row is None:
                result["fatal"] = "xrayTemplateConfig missing; never auto-seed"
                return result
            cfg = json.loads(row[0])
            if not isinstance(cfg, dict):
                raise ValueError("template not dict")
            outbounds = cfg.get("outbounds")
            routing = cfg.get("routing")
            result["xray_template_valid_json"] = (
                isinstance(outbounds, list) and isinstance(routing, dict)
            )
            rules = routing.get("rules", []) if isinstance(routing, dict) else []
            if isinstance(rules, list):
                result["api_routing_rules_present"] = any(
                    isinstance(r, dict)
                    and "api" in (r.get("inboundTag") or [])
                    for r in rules
                )
            # Safe table introspection; never select client UUID/credentials.
            columns = {r[1] for r in conn.execute(
                'PRAGMA table_info("inbounds")'
            )}
            if "port" not in columns:
                result["fatal"] = "port column missing"
                return result
            result["public_443_inbounds"] = conn.execute(
                'SELECT count(*) FROM "inbounds" WHERE "port"=?',
                (443,)
            ).fetchone()[0]
    except (sqlite3.Error, ValueError, TypeError, KeyError) as e:
        result["fatal"] = "cannot validate runtime template: " + type(e).__name__
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default="/etc/x-ui/x-ui.db")
    p.add_argument("--xui-bin", default="/usr/local/x-ui/x-ui")
    args = p.parse_args()
    result = inspect(args.db, args.xui_bin)
    ready = (
        "fatal" not in result
        and result["version_exact_2_9_4"]
        and result["database_readable"]
        and result["xray_template_valid_json"]
        and result["api_routing_rules_present"]
        and result["public_443_inbounds"] == 1
    )
    result["safe_to_plan_staged_adapter"] = ready
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not ready:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
