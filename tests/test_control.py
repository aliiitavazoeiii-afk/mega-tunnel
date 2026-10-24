import unittest
from mega_tunnel.control import Coordinator, Rejected, Stage
from mega_tunnel.models import reference_inventory, Transport


class ReplacementTests(unittest.TestCase):
    def setUp(self):
        self.c = Coordinator(reference_inventory())
        self.fp = "sha256:" + "a" * 64

    def new(self):
        return self.c.propose("F1", transport=Transport.NAIVE,
                              candidate_fingerprint=self.fp, operator_confirmed=True)

    def test_both_gateways_must_prepare_and_apply(self):
        p = self.new()
        gen = p.target_generation
        self.c.prepare_ack("Maya1", gen, verified=True)
        with self.assertRaises(Rejected):
            self.c.commit(gen)
        self.c.prepare_ack("Maya3", gen, verified=True)
        self.assertEqual(p.stage, Stage.READY)
        self.c.commit(gen)
        self.c.apply_ack("Maya1", gen, verified=True)
        self.assertEqual(p.stage, Stage.PARTIAL)
        with self.assertRaises(Rejected):
            self.c.begin_drain(gen)
        self.c.apply_ack("Maya3", gen, verified=True)
        self.assertEqual(p.stage, Stage.APPLIED)
        self.c.begin_drain(gen)
        with self.assertRaises(Rejected):
            self.c.finish(gen, drained=True, cleanup_approved=False)
        self.assertEqual(p.stage, Stage.DRAINING)
        self.c.finish(gen, drained=True, cleanup_approved=True)
        self.assertEqual(p.stage, Stage.COMPLETE)

    def test_second_replacement_increases_generation(self):
        first = self.new()
        gen = first.target_generation
        for g in ("Maya1", "Maya3"):
            self.c.prepare_ack(g, gen, verified=True)
        self.c.commit(gen)
        for g in ("Maya1", "Maya3"):
            self.c.apply_ack(g, gen, verified=True)
        self.c.begin_drain(gen)
        self.c.finish(gen, drained=True, cleanup_approved=True)
        self.assertEqual(self.c.inventory.generation, gen)
        second = self.new()
        self.assertEqual(second.target_generation, gen + 1)

    def test_fail_prepare_keeps_old(self):
        p = self.new()
        self.c.prepare_ack("Maya1", p.target_generation, verified=False)
        self.assertEqual(p.stage, Stage.ABORTED)
        self.assertTrue(p.prior_retained)
        with self.assertRaises(Rejected):
            self.c.commit(p.target_generation)

    def test_failed_apply_cannot_claim_complete(self):
        p = self.new()
        for g in ("Maya1", "Maya3"):
            self.c.prepare_ack(g, p.target_generation, verified=True)
        self.c.commit(p.target_generation)
        self.c.apply_ack("Maya3", p.target_generation, verified=False)
        self.assertEqual(p.stage, Stage.PARTIAL)
        with self.assertRaises(Rejected):
            self.c.finish(p.target_generation, drained=True, cleanup_approved=True)

    def test_wrong_transport_rejected(self):
        with self.assertRaises(Rejected):
            self.c.propose("F1", transport=Transport.XHTTP_REALITY,
                           candidate_fingerprint=self.fp, operator_confirmed=True)

    def test_stale_generation_rejected(self):
        self.new()
        with self.assertRaises(Rejected):
            self.c.prepare_ack("Maya1", 999, verified=True)

    def test_another_replacement_cannot_preempt(self):
        self.new()
        with self.assertRaises(Rejected):
            self.new()

    def test_explicit_operator_confirmation(self):
        with self.assertRaises(Rejected):
            self.c.propose("F1", transport=Transport.NAIVE,
                           candidate_fingerprint=self.fp, operator_confirmed=False)

    def test_unknown_gateway_ack_rejected(self):
        p = self.new()
        with self.assertRaises(Rejected):
            self.c.prepare_ack("unknown", p.target_generation, verified=True)
