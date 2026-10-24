import unittest
from mega_tunnel.models import Edge, EdgeState, reference_inventory, TrafficSnapshot
from mega_tunnel.routing import Router, NoHealthyRoute, StaleMetrics

GB = 1000 ** 3


def edges(state_by_pair=None):
    inv = reference_inventory()
    state_by_pair = state_by_pair or {}
    return [
        Edge(g, f, state_by_pair.get((g, f), EdgeState.HEALTHY),
             rtt_ms=150, error_rate=0, active_connections=100)
        for g in inv.gateways for f in inv.foreigns
    ]


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.inv = reference_inventory()
        self.router = Router(self.inv)
        self.traffic = TrafficSnapshot({f: 100 * GB for f in self.inv.foreigns})

    def test_primaries_only_when_healthy(self):
        for g, accepted in [("Maya1", {"F1", "F2"}), ("Maya3", {"F3", "F4"})]:
            d = self.router.choose(g, edges(), self.traffic, flow_affinity="test")
            self.assertIn(d.foreign_id, accepted)
            self.assertFalse(d.emergency)

    def test_edge_specific_filter_does_not_remove_node_globally(self):
        blocked = {("Maya1", "F1"): EdgeState.QUARANTINED}
        a = self.router.choose("Maya1", edges(blocked), self.traffic)
        self.assertEqual(a.foreign_id, "F2")
        # Maya3 sees all four routes as independently healthy.
        b = self.router.choose("Maya3", edges(blocked), self.traffic)
        self.assertIn(b.foreign_id, {"F3", "F4"})

    def test_cross_gateway_emergency(self):
        blocked = {("Maya1", "F1"): EdgeState.QUARANTINED,
                   ("Maya1", "F2"): EdgeState.QUARANTINED}
        d = self.router.choose("Maya1", edges(blocked), self.traffic)
        self.assertIn(d.foreign_id, {"F3", "F4"})
        self.assertTrue(d.emergency)

    def test_disallow_emergency(self):
        blocked = {("Maya1", "F1"): EdgeState.QUARANTINED,
                   ("Maya1", "F2"): EdgeState.QUARANTINED}
        with self.assertRaises(NoHealthyRoute):
            self.router.choose("Maya1", edges(blocked), self.traffic,
                               allow_emergency=False)

    def test_no_unsafe_fallback_on_full_outage(self):
        bad = {("Maya1", f): EdgeState.QUARANTINED for f in self.inv.foreigns}
        with self.assertRaises(NoHealthyRoute):
            self.router.choose("Maya1", edges(bad), self.traffic)

    def test_stale_global_bytes_reject_cross_gateway_failover(self):
        bad = {("Maya1", "F1"): EdgeState.QUARANTINED,
               ("Maya1", "F2"): EdgeState.QUARANTINED}
        stale = TrafficSnapshot(self.traffic.bytes_by_foreign, global_metrics_fresh=False)
        with self.assertRaises(StaleMetrics):
            self.router.choose("Maya1", edges(bad), stale)

    def test_capacity_limit(self):
        overloaded = dict(self.traffic.bytes_by_foreign)
        overloaded["F1"] = 300 * GB
        d = self.router.choose("Maya1", edges(), TrafficSnapshot(overloaded))
        self.assertEqual(d.foreign_id, "F2")

    def test_affinity_if_healthy(self):
        d = self.router.choose("Maya1", edges(), self.traffic,
                               sticky_foreign_id="F2")
        self.assertEqual(d.foreign_id, "F2")
        self.assertEqual(d.reason, "healthy-sticky")

    def test_sticky_must_not_pin_to_failed(self):
        d = self.router.choose("Maya1", edges({("Maya1","F2"): EdgeState.QUARANTINED}),
                               self.traffic, sticky_foreign_id="F2")
        self.assertEqual(d.foreign_id, "F1")

    def test_no_overcapacity_sticky(self):
        full = dict(self.traffic.bytes_by_foreign)
        full["F2"] = 301 * GB
        d = self.router.choose("Maya1", edges(), TrafficSnapshot(full),
                               sticky_foreign_id="F2")
        self.assertEqual(d.foreign_id, "F1")

    def test_unknown_gateway(self):
        with self.assertRaises(ValueError):
            self.router.choose("Maya4", edges(), self.traffic)
