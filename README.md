# Mega Tunnel

**Dual Iran gateways / four foreign nodes / two independent TCP transports / safe control plane.**

> **STATUS: DESIGN + VERIFIED DOMAIN-LOGIC IMPLEMENTATION (NOT PRODUCTION-READY).** No changes have been made to Maya1, Maya3 or the existing `frp-tunnel` installation. No code in this repository should be installed on a live VPN gateway until the release gates in `docs/ACCEPTANCE.md` have passed.

## Fixed topology

- **Maya1:** ~145 users; primary F1 (NaiveProxy) + F2 (XHTTP/REALITY).
- **Maya3:** ~145 users; primary F3 (NaiveProxy) + F4 (XHTTP/REALITY).
- Each Iran gateway can use **all four** foreign nodes in a capacity-controlled **emergency** mode.
- Approx. **500 GB/day** across ~290 clients. Budget: **four foreign machines**, no Cloudflare and no Bridge.
- Existing user VLESS/REALITY addresses/subscriptions and x-ui **2.9.4** must be preserved.
- Server-to-server transport **TCP only**. Client UDP is a separate, explicitly tested capability; it is **not silently discarded**.

## Non-negotiable design rules

Read `docs/REQUIREMENTS.md`, `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/ACCEPTANCE.md`, and `docs/OPERATIONS.md` **before** changes. The no-downgrade policy applies to all patches and emergency fixes.

### One-place foreign replacement

Dashboard → select F1–F4 → register replacement → install on new foreign from a **version-pinned, authenticated** installer → test from BOTH Iran gateways → prepare both → atomic generation change / verify acknowledgements → start new connections → drain old → explicitly approve old-node cleanup.

A replacement is a **logical foreign node ID**, not a mutable IP in two unrelated local files. Both Maya1 and Maya3 derive from the same versioned inventory. Never turn off the old node until the new node is verified, committed and recoverable.

## Repository modules

- `mega_tunnel/`: dependency-free *domain model* and deterministic health, capacity and routing decision logic. Not a network tunnel daemon.
- `tests/`: unit tests of invariants and failure logic.
- `dashboard/`: non-operational UI prototype, not connected to production servers.
- `docs/`: architecture, security invariants, rollout and delivery gates.
- `deploy/`: reserved for signed, pinned installers and systemd units once transport integration and authentication have been verified.

## Development

```bash
python3 -m unittest discover -s tests -v
```

Production requires: authenticated mTLS agents, real Naive/XHTTP adapters, a durable transactional controller, metrics, actual integration/fault tests, hardened foreign installer, signed releases, a production-grade secured dashboard, and staged deployment. These are **not** claimed complete.

## Secrets

This is a public repository. **Never commit** IP inventory, private keys, UUIDs, credential bundles, controller tokens, user lists or x-ui databases. `.gitignore` is defense-in-depth, not a substitute for review.
