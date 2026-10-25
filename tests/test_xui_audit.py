import importlib.util
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "xui_audit",
    Path(__file__).resolve().parents[1] / "ops" / "audit-xui294.py"
)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class XuiAuditTests(unittest.TestCase):
    def create_fixture(self, dirname, version="2.9.4", port=443, template=True):
        binfile = Path(dirname) / "x-ui"
        binfile.write_text("#!/bin/sh\necho 3x-ui version " + version + "\n")
        binfile.chmod(0o755)
        db = Path(dirname) / "x-ui.db"
        with sqlite3.connect(db) as con:
            con.execute("CREATE TABLE settings(key TEXT, value TEXT)")
            con.execute("CREATE TABLE inbounds(port INTEGER)")
            con.execute("INSERT INTO inbounds VALUES (?)", (port,))
            if template:
                con.execute("INSERT INTO settings VALUES (?, ?)", (
                    "xrayTemplateConfig",
                    json.dumps({
                        "outbounds": [{"tag": "direct"}],
                        "routing": {"rules": [{"inboundTag": ["api"], "outboundTag": "api"}]},
                        "private_key": "NEVER_DISPLAY_THIS"
                    })
                ))
        return str(db), str(binfile)

    def test_success_with_valid_structure(self):
        with tempfile.TemporaryDirectory() as d:
            db, b = self.create_fixture(d)
            result = audit.inspect(db, b)
            self.assertTrue(result["version_exact_2_9_4"])
            self.assertEqual(result["xray_template_source"], "database_saved")
            self.assertEqual(result["inbounds_total"], 1)
            self.assertEqual(result["inbound_ports_sample"], [443])
            self.assertTrue(result["api_routing_rules_present"])
            self.assertEqual(result["public_443_inbounds"], 1)
            self.assertNotIn("NEVER_DISPLAY_THIS", json.dumps(result))

    def test_wrong_version_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            db, b = self.create_fixture(d, version="2.9.5")
            result = audit.inspect(db, b)
            self.assertFalse(result["version_exact_2_9_4"])
            self.assertIn("fatal", result)

    def test_missing_template_never_seeded(self):
        with tempfile.TemporaryDirectory() as d:
            db, b = self.create_fixture(d, template=False)
            result = audit.inspect(db, b)
            self.assertNotIn("fatal", result)
            self.assertEqual(result["xray_template_source"], "built_in_default_possible")
            self.assertIsNone(result["xray_template_valid_json"])
            self.assertIsNone(result["api_routing_rules_present"])
            self.assertFalse(result.get("safe_to_plan_staged_adapter", False))
            self.assertEqual(result["inbounds_total"], 1)
            self.assertEqual(result["public_443_inbounds"], 1)
            with sqlite3.connect(db) as con:
                self.assertEqual(
                    con.execute("SELECT count(*) FROM settings").fetchone()[0], 0
                )

    def test_missing_port_not_compatible(self):
        with tempfile.TemporaryDirectory() as d:
            db, b = self.create_fixture(d, port=8443)
            result = audit.inspect(db, b)
            self.assertEqual(result["public_443_inbounds"], 0)
