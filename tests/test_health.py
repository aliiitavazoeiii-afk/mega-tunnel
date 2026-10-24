import unittest
from mega_tunnel.health import Circuit
from mega_tunnel.models import EdgeState


class CircuitTests(unittest.TestCase):
    def test_quarantine_and_cooldown(self):
        c = Circuit(cooldown_s=30)
        self.assertEqual(c.observe(False, 1), EdgeState.HEALTHY)
        self.assertEqual(c.observe(False, 2), EdgeState.SUSPECT)
        self.assertFalse(c.admits_new_flows)
        c.observe(False, 3)
        self.assertEqual(c.observe(False, 4), EdgeState.QUARANTINED)
        self.assertEqual(c.observe(True, 10, active_probe=True), EdgeState.QUARANTINED)
        self.assertEqual(c.observe(True, 34, active_probe=True), EdgeState.PROBATION)
        self.assertFalse(c.admits_new_flows)
        self.assertEqual(c.observe(True, 35, active_probe=True), EdgeState.PROBATION)
        self.assertEqual(c.observe(True, 36, active_probe=True), EdgeState.HEALTHY)

    def test_suspect_requires_active_verification(self):
        c = Circuit()
        c.observe(False, 1)
        c.observe(False, 2)
        self.assertEqual(c.observe(True, 3), EdgeState.SUSPECT)
        self.assertEqual(c.observe(True, 4, active_probe=True), EdgeState.HEALTHY)

    def test_recovery_failure_requarantines(self):
        c = Circuit()
        for i in range(4):
            c.observe(False, i)
        self.assertEqual(c.observe(False, 65, active_probe=True), EdgeState.QUARANTINED)

    def test_healthy_secondary_is_independent(self):
        a, b = Circuit(), Circuit()
        for i in range(4):
            a.observe(False, i)
        self.assertEqual(a.state, EdgeState.QUARANTINED)
        self.assertEqual(b.state, EdgeState.HEALTHY)
