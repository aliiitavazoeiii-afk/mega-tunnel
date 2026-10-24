"""Safe per-flow *decision* model, not a TCP proxy or network daemon."""
from dataclasses import dataclass
from typing import Dict, Iterable, Optional
import hashlib
from .models import Edge, EdgeState, Inventory, TrafficSnapshot


class NoHealthyRoute(RuntimeError):
    pass


class StaleMetrics(RuntimeError):
    pass


@dataclass(frozen=True)
class Decision:
    gateway: str
    foreign_id: str
    generation: int
    emergency: bool
    reason: str


class Router:
    def __init__(self, inventory: Inventory):
        inventory.validate()
        self.inventory = inventory

    def choose(
        self, gateway: str, edges: Iterable[Edge],
        traffic: TrafficSnapshot, *,
        sticky_foreign_id: Optional[str] = None,
        flow_affinity: str = "",
        allow_emergency: bool = True,
    ) -> Decision:
        if gateway not in self.inventory.gateways:
            raise ValueError("unknown gateway")
        by_node: Dict[str, Edge] = {e.foreign_id: e for e in edges if e.gateway == gateway}
        valid = []
        for foreign_id, foreign in self.inventory.foreigns.items():
            e = by_node.get(foreign_id)
            if e is None or not e.reachable or e.state != EdgeState.HEALTHY:
                continue
            # The foreign-wide byte budget is already aggregate across BOTH gateways.
            bytes_today = traffic.bytes_by_foreign.get(foreign_id)
            if bytes_today is None:
                continue
            if bytes_today >= foreign.capacity_bytes_per_day:
                continue
            if e.active_connections >= foreign.max_connections:
                continue
            if e.canary_weight <= 0:
                continue
            valid.append(e)

        primary = [e for e in valid if e.foreign_id in self.inventory.primary[gateway]]
        # Avoid cross-gateway emergency use on stale global counters.
        if not primary and valid and allow_emergency and not traffic.global_metrics_fresh:
            raise StaleMetrics("cannot arbitrate shared foreign capacity with stale metrics")

        if primary:
            pool = primary
            emergency = False
        elif allow_emergency and traffic.global_metrics_fresh:
            pool = valid
            emergency = True
        else:
            pool = []
            emergency = False

        if not pool:
            raise NoHealthyRoute("no approved, healthy, within-budget route")

        # Existing session affinity remains ONLY while candidate is healthy and within cap.
        if sticky_foreign_id and any(e.foreign_id == sticky_foreign_id for e in pool):
            return Decision(gateway, sticky_foreign_id, self.inventory.generation,
                            emergency, "healthy-sticky")

        def score(e: Edge) -> tuple:
            f = self.inventory.foreigns[e.foreign_id]
            # The dominant term is combined node byte utilization, not number of users.
            utilization = traffic.bytes_by_foreign[e.foreign_id] / f.capacity_bytes_per_day
            conn_pressure = e.active_connections / f.max_connections
            penalty = e.error_rate * 2 + min(e.rtt_ms / 1500, 1) * 0.15
            # Deterministic small jitter avoids thundering-herd ties, never overrules load.
            digest = hashlib.sha256((flow_affinity + "|" + e.foreign_id).encode()).digest()
            jitter = int.from_bytes(digest[:4], "big") / 2 ** 32 * 0.001
            return (utilization + conn_pressure * 0.25 + penalty
                    - e.canary_weight * 0.02 + jitter, e.foreign_id)

        winner = min(pool, key=score)
        return Decision(gateway, winner.foreign_id,
                        self.inventory.generation, emergency, "capacity-health-score")
