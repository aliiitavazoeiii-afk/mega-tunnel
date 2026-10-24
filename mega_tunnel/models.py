"""Immutable topology and live edge metrics; no secrets or network calls."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet, Tuple


class Transport(str, Enum):
    NAIVE = "naive"
    XHTTP_REALITY = "xhttp-reality"


class EdgeState(str, Enum):
    HEALTHY = "healthy"
    SUSPECT = "suspect"
    QUARANTINED = "quarantined"
    PROBATION = "probation"


@dataclass(frozen=True)
class Foreign:
    id: str
    transport: Transport
    # Inclusive of both Iranian gateways' traffic, not per-gateway.
    capacity_bytes_per_day: int
    max_connections: int

    def __post_init__(self):
        if self.capacity_bytes_per_day <= 0 or self.max_connections <= 0:
            raise ValueError("foreign capacity and max_connections must be positive")


@dataclass(frozen=True)
class Edge:
    gateway: str
    foreign_id: str
    state: EdgeState
    rtt_ms: float
    error_rate: float
    active_connections: int
    canary_weight: float = 1.0
    reachable: bool = True

    def __post_init__(self):
        if not 0 <= self.error_rate <= 1:
            raise ValueError("error_rate must be [0,1]")
        if not 0 <= self.canary_weight <= 1:
            raise ValueError("canary_weight must be [0,1]")
        if self.active_connections < 0 or self.rtt_ms < 0:
            raise ValueError("invalid edge counters")


@dataclass(frozen=True)
class TrafficSnapshot:
    # The combined, authoritative foreign byte counters from Maya1 + Maya3.
    bytes_by_foreign: Dict[str, int]
    # The controller must reject cross-gateway emergency routing if these are stale.
    global_metrics_fresh: bool = True


@dataclass(frozen=True)
class Inventory:
    generation: int
    gateways: Tuple[str, ...]
    foreigns: Dict[str, Foreign]
    primary: Dict[str, FrozenSet[str]]

    def validate(self) -> None:
        if self.generation < 1:
            raise ValueError("generation must start at 1")
        if set(self.gateways) != {"Maya1", "Maya3"} or len(self.gateways) != 2:
            raise ValueError("expected exactly Maya1 and Maya3")
        if set(self.foreigns) != {"F1", "F2", "F3", "F4"}:
            raise ValueError("expected precisely four logical foreign IDs")
        if set(self.primary) != set(self.gateways):
            raise ValueError("missing gateway primaries")
        for g in self.gateways:
            if len(self.primary[g]) != 2 or not self.primary[g] <= self.foreigns.keys():
                raise ValueError("each gateway needs exactly two valid primaries")
            if {self.foreigns[n].transport for n in self.primary[g]} != set(Transport):
                raise ValueError("each gateway needs two distinct transports")
        if self.primary["Maya1"] & self.primary["Maya3"]:
            raise ValueError("normal primary pools must be disjoint")


def reference_inventory() -> Inventory:
    gb = 1000 ** 3
    inventory = Inventory(
        generation=1,
        gateways=("Maya1", "Maya3"),
        foreigns={
            "F1": Foreign("F1", Transport.NAIVE, 300 * gb, 5000),
            "F2": Foreign("F2", Transport.XHTTP_REALITY, 300 * gb, 5000),
            "F3": Foreign("F3", Transport.NAIVE, 300 * gb, 5000),
            "F4": Foreign("F4", Transport.XHTTP_REALITY, 300 * gb, 5000),
        },
        primary={
            "Maya1": frozenset(("F1", "F2")),
            "Maya3": frozenset(("F3", "F4")),
        }
    )
    inventory.validate()
    return inventory
