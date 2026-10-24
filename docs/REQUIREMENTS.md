# Mega Tunnel — immutable product and safety requirements

These are product invariants, not optional feature requests. Any change weakening one requires explicit user approval, a threat-model revision and a measured A/B test. **Fail closed** rather than substituting a simpler but weaker design.

## Topology / budget
- R01: Exactly two live Iran gateways, Maya1 and Maya3, each initially serving ~145 users.
- R02: Exactly four existing foreign machines, F1..F4. No paid fifth server, CDN or Bridge dependency in V1.
- R03: F1/Naive and F2/XHTTP are Maya1 primaries; F3/Naive and F4/XHTTP are Maya3 primaries.
- R04: All four nodes provisioned as eligible emergency destinations for BOTH gateways; cross-gateway sharing is capacity-guarded.
- R05: Expected total 490–500 GB/day, measure actual egress bytes (not user count or connection count), report per-node and per-Iran contribution.
- R06: No UDP on Iran-to-foreign links; client application UDP explicitly tracked/tested separately.

## Reliability / security
- R07: No central/shared tunnel data-path process whose restart simultaneously disconnects both healthy transports.
- R08: No autoheal loops restarting healthy services, no global x-ui restart for a foreign swap, and no automatically deleting old foreign configurations.
- R09: Health is PER (Iran gateway, foreign node, transport) edge; one filtered route must not evict an otherwise reachable node globally.
- R10: Passive error-rate/timeout/RTT signals plus bounded, low-noise active probes; HEALTHY/SUSPECT/QUARANTINED/PROBATION with hysteresis.
- R11: Circuit breaker quarantines new flow selection; existing TCP sockets may fail and must reconnect. Never promise transparent migration.
- R12: Real capacity ceilings, emergency reserve, gradual reintroduction, stickiness for IP-sensitive sessions; do not use simple round robin.
- R13: If every route fails, report the outage; NEVER fall back to an unauthenticated, cleartext or unapproved direct route.
- R14: Authenticated and encrypted control traffic (mutual device identity) and authenticated encrypted data transport; no exposed no-auth management endpoints.
- R15: Prevent public disclosure of foreign IPs, UUIDs, passwords, REALITY keys, user data, inventory or admin access.
- R16: No homemade encryption or unverifiable claims of DPI invisibility. The network can observe IP, total bytes and flow timing. Do not inject high-volume fake traffic or rely on a single fingerprint.
- R17: Preserve existing x-ui 2.9.4 and VLESS/REALITY inbound 443 and client configurations; preflight the *actual* deployed version.
- R18: Independent transport implementations: NaiveProxy/HTTPS-TCP and Xray XHTTP/REALITY-TCP, after integration and regression testing.

## Control plane / UX
- R19: Dashboard presents both Iran gateways, four shared logical foreign IDs, transport type, edge-specific status, active flow count, today bytes, errors, state, quota and last failover.
- R20: Replace F1..F4 via dashboard with a single foreign bootstrap command and no client-config edit.
- R21: Replacement must update BOTH Iran gateways using a monotonic signed configuration generation, with prepare/validate/commit/ack and rollback/reconciliation.
- R22: Never declare 'replacement complete' if either Iran gateway has not acknowledged target generation. Automatic reconciliation and human-readable partial-deployment status.
- R23: One-time short-lived enrollment credentials, pinned/verifiable artifact digests, certificate/key rotation, RBAC, step-up confirmation, CSRF protection, audit trail; absolutely no secrets in command output or GitHub.
- R24: New node canary, staged weight ramp, graceful old-flow drain; explicit operator approval before old-server teardown.
- R25: Admin UI must be simple and Persian-friendly without hiding danger states; show preview/dry-run/confirm/rollback.
- R26: A disconnected controller must not interrupt established data plane; agents operate with last-known-good signed config. Mutations fail closed during split-brain.

## Verification / operations
- R27: Integration tests for gateway → both transport types → four foreign nodes, real TCP load, Telegram, YouTube, HTTP/2, mobile apps and long-lived connections.
- R28: Failure injection: IP filtered on only one Iran edge, loss of F1/2/3/4, partition between Iran gateways, slow path, jitter, DNS failure, restart, expired enrollment, stale config generation, and controller outage.
- R29: Safe parallel pilot before any user migration; all steps must have checkpoint, canary and documented rollback.
- R30: Strict delivery state in `docs/STATUS.md`; specifications and mocked UI must never be described as working production implementation.
