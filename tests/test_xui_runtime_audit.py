import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "xui_runtime_audit",
    Path(__file__).resolve().parents[1] / "ops" / "audit-xui294-runtime.py"
)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class RuntimeAuditTests(unittest.TestCase):
    def fixture(self, tmpdir, *, with_clients=True, template=False):
        root = Path(tmpdir)
        db = root / "x-ui.db"
        with sqlite3.connect(db) as conn:
            conn.execute("CREATE TABLE settings(key TEXT, value TEXT)")
            conn.execute(
                "CREATE TABLE inbounds(port INTEGER, enable INTEGER, "
                "protocol TEXT, settings TEXT, stream_settings TEXT)"
            )
            conn.execute("CREATE TABLE client_traffics(enable INTEGER, email TEXT)")
            secrets = {
                "clients": [
                    {"id": "SECRET_UUID_001", "email": "private1@example.org",
                     "enable": True, "password": "SECRET_PASSWORD"} ,
                    {"id": "SECRET_UUID_002", "email": "private2@example.org",
                     "enable": False},
                ] if with_clients else []
            }
            stream = {
                "network": "tcp",
                "security": "reality",
                "realitySettings": {"privateKey": "SECRET_REALITY_KEY"},
            }
            conn.execute(
                "INSERT INTO inbounds VALUES (?,?,?,?,?)",
                (443, 1, "vless", json.dumps(secrets), json.dumps(stream))
            )
            conn.execute("INSERT INTO client_traffics VALUES (?,?)", (1, "hidden@example.org"))
            if template:
                conn.execute("INSERT INTO settings VALUES (?, ?)",
                             ("xrayTemplateConfig", "secret"))
        return str(db)

    def test_privacy_and_nonmutating(self):
        with tempfile.TemporaryDirectory() as d:
            db = self.fixture(d)
            listeners = {"443": True, "62789": True, "11111": True}
            res = AUDIT.inspect(db, "/unused/x-ui",
                                version_text="3x-ui 2.9.4",
                                listeners=listeners)
            self.assertEqual(res["enabled_inbounds"], 1)
            self.assertEqual(res["public_443_inbounds"], 1)
            self.assertEqual(res["clients_in_inbound_json"], 2)
            self.assertEqual(res["clients_manually_enabled_in_json"], 1)
            self.assertEqual(res["clients_manually_disabled_in_json"], 1)
            self.assertEqual(res["client_traffic_rows"], 1)
            self.assertEqual(res["client_traffic_enabled"], 1)
            self.assertEqual(res["template_source"], "built_in_default_possible")
            self.assertFalse(res["safe_to_change_xui"])
            serialized = json.dumps(res)
            for secret in ("SECRET_", "private1", "hidden@example.org"):
                self.assertNotIn(secret, serialized)
            with sqlite3.connect(db) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM inbounds").fetchone()[0], 1)

    def test_wrong_version_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            db = self.fixture(d)
            res = AUDIT.inspect(db, "/unused", version_text="3x-ui 2.9.5",
                                listeners={})
            self.assertIn("error", res)
            self.assertFalse(res["database_readable"])

    def test_saved_template_does_not_echo_value(self):
        with tempfile.TemporaryDirectory() as d:
            db = self.fixture(d, template=True)
            res = AUDIT.inspect(db, "/unused", version_text="2.9.4",
                                listeners={})
            self.assertEqual(res["template_source"], "database_saved")
            self.assertFalse(res["safe_to_change_xui"])
            self.assertNotIn("SECRET", json.dumps(res))
