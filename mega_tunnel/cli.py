"""Offline-only preflight / example planner: never touches Maya1 or Maya3."""
import argparse
import json
from .models import reference_inventory, Edge, EdgeState, TrafficSnapshot
from .routing import Router, NoHealthyRoute


def demo():
    inv = reference_inventory()
    snap = TrafficSnapshot({f: 125 * 1000 ** 3 for f in inv.foreigns})
    edges = [
        Edge(g, f, EdgeState.HEALTHY, 150, 0, 80)
        for g in inv.gateways for f in inv.foreigns
    ]
    output = {
        "mode": "OFFLINE-DEMO-NO-NETWORK-CHANGES",
        "generation": inv.generation,
        "decisions": [
            Router(inv).choose(g, edges, snap, flow_affinity=g + "-sample").__dict__
            for g in inv.gateways
        ],
    }
    print(json.dumps(output, indent=2))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["demo"])
    a = p.parse_args()
    if a.action == "demo":
        demo()


if __name__ == "__main__":
    main()
