import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SPEC = importlib.util.spec_from_file_location(
    "xui_mega_bridge",
    Path(__file__).resolve().parents[1] / "ops" / "connect-xui-to-mega.py"
)
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


class XuiMegaBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "x-ui.db"
        self.vendor = self.root / "default.json"
        self.backups = self.root / "backups"
        self.state = self.root / "state.json"
        self.statedir = self.root / "state"
        self.statedir.mkdir()
        self.vendor.write_text(json.dumps({
            "api": {"tag": "api"},
            "inbounds": [{"tag": "api", "port": 62789}],
            "metrics": {"listen": "127.0.0.1:11111"},
            "outbounds": [
                {"tag": "direct", "protocol": "freedom"},
                {"tag": "blocked", "protocol": "blackhole"}
            ],
            "routing": {"domainStrategy": "AsIs", "rules": [
                {"type": "field", "inboundTag": ["api"], "outboundTag": "api"},
                {"type": "field", "ip": ["geoip:private"], "outboundTag": "blocked"}
            ]}
        }))
        with sqlite3.connect(self.db) as con:
            con.execute("CREATE TABLE settings(key TEXT, value TEXT)")
            con.execute('CREATE TABLE inbounds ("port" INTEGER,"enable" INTEGER,'
                        '"protocol" TEXT,"settings" TEXT,"stream_settings" TEXT,'
                        '"tag" TEXT,"listen" TEXT,"sniffing" TEXT)')
            con.execute(
                "INSERT INTO inbounds VALUES (?,?,?,?,?,?,?,?)",
                (443, 1, "vless",
                 json.dumps({"clients": [
                     {"email": "PRIVATE@example.org", "id": "SECRET_UUID",
                      "enable": True, "flow": "xtls-rprx-vision"}]}),
                 json.dumps({
                     "network": "tcp", "security": "reality",
                     "realitySettings": {"privateKey": "SECRET_KEY"}
                 }), "inbound-private-tag", "", "{}")
            )
        for name, new in (("DB", self.db), ("VENDOR", self.vendor),
                          ("BACKUPDIR", self.backups), ("STATEDIR", self.statedir),
                          ("STATEFILE", self.state)):
            patcher = mock.patch.object(bridge, name, new)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _setting(self):
        with sqlite3.connect(self.db) as con:
            return bridge.read_setting(con)

    def test_routing_preserves_api_blocks_and_inbound(self):
        with sqlite3.connect(self.db) as con:
            inbound, tag, count = bridge.load_inbound(con)
        self.assertEqual(tag, "inbound-private-tag")
        self.assertEqual(count, 1)
        candidate = bridge.build_candidate(bridge.vendor_template(), tag)
        self.assertEqual([x["tag"] for x in candidate["outbounds"]],
                         ["direct", "blocked", "mega-router"])
        self.assertEqual(candidate["outbounds"][-1]["settings"], {
            "servers": [{"address": "127.0.0.1", "port": 17990}]
        })
        rules = candidate["routing"]["rules"]
        self.assertEqual(rules[0]["outboundTag"], "api")
        self.assertEqual(rules[1]["outboundTag"], "blocked")
        self.assertEqual(rules[-2]["network"], "tcp")
        self.assertEqual(rules[-2]["inboundTag"], ["inbound-private-tag"])
        self.assertEqual(rules[-2]["outboundTag"], "mega-router")
        self.assertEqual(rules[-1]["network"], "udp")
        self.assertEqual(rules[-1]["outboundTag"], "blocked")
        self.assertNotIn("SECRET", json.dumps(candidate))
        expanded = bridge.candidate_xray_config(candidate, inbound)
        self.assertIn("SECRET_KEY", json.dumps(expanded))
        self.assertEqual(expanded["inbounds"][-1]["port"], 443)

    def test_apply_and_rollback_only_template_row(self):
        with mock.patch.object(bridge, "preflight"), \
             mock.patch.object(bridge, "xray_parse_test"), \
             mock.patch.object(bridge, "restart_and_validate", return_value=True):
            bridge.apply()
            row = self._setting()
            self.assertIsNotNone(row)
            self.assertEqual(json.loads(row[0])["outbounds"][-1]["tag"],
                             "mega-router")
            self.assertTrue(self.state.exists())
            self.assertTrue(self.backups.exists())
            # Existing 144 profiles must not be touched by this adapter.
            with sqlite3.connect(self.db) as con:
                unchanged = con.execute(
                    'SELECT "settings" FROM "inbounds"'
                ).fetchone()[0]
            self.assertIn("SECRET_UUID", unchanged)
            bridge.run_rollback()
            self.assertIsNone(self._setting())
            self.assertFalse(self.state.exists())

    def test_preexisting_custom_template_never_overwritten(self):
        with sqlite3.connect(self.db) as con:
            con.execute('INSERT INTO "settings" ("key","value") VALUES (?,?)',
                        ("xrayTemplateConfig", "private-customer-template"))
        with mock.patch.object(bridge, "preflight"):
            with self.assertRaisesRegex(RuntimeError, "Custom"):
                bridge.apply()
        self.assertEqual(self._setting()[0], "private-customer-template")

    def test_rollback_refuses_newer_owner_edits(self):
        with mock.patch.object(bridge, "preflight"), \
             mock.patch.object(bridge, "xray_parse_test"), \
             mock.patch.object(bridge, "restart_and_validate", return_value=True):
            bridge.apply()
            bridge.set_template("owner-new-settings")
            with self.assertRaisesRegex(RuntimeError, "changed after"):
                bridge.run_rollback()
            self.assertEqual(self._setting()[0], "owner-new-settings")
