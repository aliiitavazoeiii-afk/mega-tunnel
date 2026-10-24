import unittest
from dataclasses import replace
from mega_tunnel.models import reference_inventory, Transport, Foreign


class InventoryTests(unittest.TestCase):
    def test_four_foreign_two_gateways(self):
        inv = reference_inventory()
        inv.validate()
        self.assertEqual(len(inv.foreigns), 4)
        self.assertEqual(len(inv.gateways), 2)

    def test_two_distinct_transport_primaries(self):
        inv = reference_inventory()
        for g in inv.gateways:
            self.assertEqual({inv.foreigns[n].transport for n in inv.primary[g]},
                             set(Transport))

    def test_invalid_topology_fails_closed(self):
        inv = reference_inventory()
        with self.assertRaises(ValueError):
            replace(inv, gateways=("Maya1",)).validate()

    def test_invalid_foreign_budget_fails(self):
        with self.assertRaises(ValueError):
            Foreign("F5", Transport.NAIVE, 0, 10)
