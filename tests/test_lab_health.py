import asyncio
import unittest

from mega_tunnel.lab_health import CarrierMonitor
from mega_tunnel.lab_proxy import LabRouter
from mega_tunnel.routing import NoHealthyRoute


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class CarrierMonitorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clock = FakeClock()
        self.ok = {17995: True, 17996: True}
        async def probe(port):
            return self.ok[port]
        self.monitor = CarrierMonitor(
            {"F1": 17995, "F2": 17996}, prober=probe,
            clock=self.clock, stale_after=150
        )

    async def test_fail_closed_until_real_probe(self):
        self.assertFalse(self.monitor.allowed("F1"))
        self.assertFalse(self.monitor.allowed("F2"))
        await self.monitor.check_all()
        self.assertTrue(self.monitor.allowed("F1"))
        self.assertTrue(self.monitor.allowed("F2"))

    async def test_failed_carrier_isolated_and_fails_over_new_flows(self):
        await self.monitor.check_all()
        self.ok[17995] = False
        await self.monitor.check_one("F1")
        self.assertFalse(self.monitor.allowed("F1"))
        self.assertTrue(self.monitor.allowed("F2"))
        router = LabRouter("Maya1", {"F1": 17995, "F2": 17996},
                           monitor=self.monitor)
        for _ in range(15):
            self.assertEqual(router.choose(set()), "F2")
        self.ok[17996] = False
        await self.monitor.check_one("F2")
        with self.assertRaises(NoHealthyRoute):
            router.choose(set())

    async def test_quarantine_requires_cooldown_and_two_probes(self):
        await self.monitor.check_all()
        self.ok[17995] = False
        await self.monitor.check_one("F1")
        await self.monitor.check_one("F1")
        self.ok[17995] = True
        await self.monitor.check_one("F1")
        self.assertFalse(self.monitor.allowed("F1"))
        self.clock.advance(61)
        await self.monitor.check_one("F1")
        self.assertFalse(self.monitor.allowed("F1"))
        await self.monitor.check_one("F1")
        self.assertTrue(self.monitor.allowed("F1"))

    async def test_stale_health_not_trusted(self):
        await self.monitor.check_all()
        self.clock.advance(151)
        self.assertFalse(self.monitor.allowed("F1"))
        self.assertFalse(self.monitor.allowed("F2"))

    async def test_local_socks_handshake_error_marks_only_one_edge(self):
        await self.monitor.check_all()
        self.monitor.report_connect_failure("F1")
        self.assertFalse(self.monitor.allowed("F1"))
        self.assertTrue(self.monitor.allowed("F2"))
