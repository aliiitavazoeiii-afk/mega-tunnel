"""Pure state machine for one logical foreign replacement across both gateways.

No network I/O, no SSH, no production controller: a correctness/test foundation.
The controller adapter must durably persist transitions, authenticate ACKs and
provide monotonic signed epochs before this can operate on real gateways.
"""
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Dict, FrozenSet
from .models import Inventory, Transport


class Stage(str, Enum):
    CANDIDATE = "candidate"
    PREPARING = "preparing"
    READY = "ready"
    COMMITTING = "committing"
    PARTIAL = "partial"
    APPLIED = "applied"
    DRAINING = "draining"
    COMPLETE = "complete"
    ABORTED = "aborted"


class Rejected(RuntimeError):
    pass


@dataclass
class Replacement:
    foreign_id: str
    target_generation: int
    transport: Transport
    candidate_fingerprint: str
    stage: Stage = Stage.CANDIDATE
    prepared: FrozenSet[str] = frozenset()
    applied: FrozenSet[str] = frozenset()
    prior_retained: bool = True
    events: list = field(default_factory=list)

    @property
    def complete_on_both(self):
        return self.applied == frozenset(("Maya1", "Maya3"))

    def _event(self, detail: str):
        self.events.append(f"{self.stage.value}: {detail}")


class Coordinator:
    def __init__(self, inventory: Inventory):
        inventory.validate()
        self.inventory = inventory
        self.pending: Replacement | None = None

    def propose(self, foreign_id: str, *, transport: Transport,
                candidate_fingerprint: str, operator_confirmed: bool) -> Replacement:
        if not operator_confirmed:
            raise Rejected("explicit operator confirmation required")
        if self.pending and self.pending.stage not in (Stage.COMPLETE, Stage.ABORTED):
            raise Rejected("another replacement is already in progress")
        foreign = self.inventory.foreigns.get(foreign_id)
        if foreign is None:
            raise Rejected("unknown logical foreign id")
        if foreign.transport != transport:
            raise Rejected("cannot downgrade or switch transport in replacement")
        if len(candidate_fingerprint) < 32:
            raise Rejected("candidate identity fingerprint missing/too short")
        p = Replacement(foreign_id, self.inventory.generation + 1,
                        transport, candidate_fingerprint, stage=Stage.PREPARING)
        p._event("candidate entered preparation; prior foreign retained")
        self.pending = p
        return p

    def prepare_ack(self, gateway: str, generation: int, *, verified: bool):
        p = self._require(generation)
        if gateway not in self.inventory.gateways:
            raise Rejected("unrecognized gateway ACK")
        if p.stage not in (Stage.PREPARING, Stage.READY):
            raise Rejected("not preparing")
        if not verified:
            p.stage = Stage.ABORTED
            p._event(f"{gateway} verification failed; old foreign retained")
            return p
        p.prepared = p.prepared | frozenset([gateway])
        if p.prepared == frozenset(self.inventory.gateways):
            p.stage = Stage.READY
        p._event(f"{gateway} prepared generation {generation}")
        return p

    def commit(self, generation: int):
        p = self._require(generation)
        if p.stage != Stage.READY or p.prepared != frozenset(self.inventory.gateways):
            raise Rejected("cannot commit until both gateways prepared")
        p.stage = Stage.COMMITTING
        p._event("commit requested; awaiting BOTH apply ACKs")
        return p

    def apply_ack(self, gateway: str, generation: int, *, verified: bool):
        p = self._require(generation)
        if p.stage not in (Stage.COMMITTING, Stage.PARTIAL, Stage.APPLIED):
            raise Rejected("no committed generation awaiting ACK")
        if gateway not in self.inventory.gateways:
            raise Rejected("unrecognized gateway ACK")
        if not verified:
            p.stage = Stage.PARTIAL
            p._event(f"{gateway} apply failed, reconciliation required")
            return p
        p.applied = p.applied | frozenset([gateway])
        p.stage = Stage.APPLIED if p.complete_on_both else Stage.PARTIAL
        p._event(f"{gateway} applied generation {generation}")
        return p

    def begin_drain(self, generation: int):
        p = self._require(generation)
        if p.stage != Stage.APPLIED or not p.complete_on_both:
            raise Rejected("cannot drain old foreign without both apply ACKs")
        p.stage = Stage.DRAINING
        p._event("old endpoint retained; graceful drain begun")
        return p

    def finish(self, generation: int, *, drained: bool, cleanup_approved: bool):
        p = self._require(generation)
        if p.stage != Stage.DRAINING or not p.complete_on_both:
            raise Rejected("cannot complete incomplete deployment")
        if not drained or not cleanup_approved:
            raise Rejected("drain and explicit old-node cleanup approval needed")
        p.stage = Stage.COMPLETE
        p._event("operator approved cleanup after drain")
        # Bump the logical generation in-memory for subsequent proposals.
        # A REAL controller must persist the signed snapshot transactionally.
        self.inventory = replace(self.inventory, generation=p.target_generation)
        return p

    def _require(self, generation: int) -> Replacement:
        p = self.pending
        if p is None or p.target_generation != generation:
            raise Rejected("unknown/stale configuration generation")
        return p
