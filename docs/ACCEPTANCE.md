# Acceptance criteria / release gates

NO live migration or replacement until all relevant gates pass with timestamps, artifacts and an operator-approved rollback.

## Gate A — source and safety
- [x] Written requirements, routing invariants, health state machine, topology, replacement state machine.
- [x] First-pass unit tests for those domain invariants.
- [ ] Static type checker / lint / signed lockfile / SBOM / pinned dependencies.
- [ ] Independent security code review and exhaustive secret scanning.
- [ ] No self-signed TLS accepted without an authenticated pin; fail closed on missing identity.

## Gate B — production transport
- [ ] Pinned NaiveProxy server/client versions and digest-verified installs, actual TLS validation.
- [ ] Pinned Xray + XHTTP + REALITY server/client versions, compatible TCP-only configuration.
- [ ] Cross-protocol transport-independent sockets; one service failure leaves the other functioning.
- [ ] Server-to-server transport never silently uses UDP.
- [ ] Reproducible 2 vCPU / 2GB and 3 vCPU / 2GB gateway benchmarks; OOM/cpu throttling under target load.

## Gate C — secured control plane and dashboard
- [ ] Controller transactional persistent store, authenticated mTLS agents, signed monotonic config generations.
- [ ] RBAC/MFA operator auth, expiring CSRF tokens, rate limits, IP restrictions, complete security audit.
- [ ] One-click logical Foreign replacement (F1–F4); short-lived single-use enrollment; one pinned foreign install command.
- [ ] Both Iran gateways run candidate preflights, prepare, commit, ACK; UI distinguishes PARTIAL / FAILED / COMPLETE.
- [ ] Server swap never edits public user profiles, never restarts x-ui globally, and retains old node until manual cleanup.
- [ ] Agent reconciles partial apply against last-known-good and controller epochs after network partition.

## Gate D — reliability and fairness
- [ ] Health per (gateway, foreign, transport), passive+active signals, stale-metrics rejection.
- [ ] Sticky destinations survive healthy service use; failover moves *new* sessions only.
- [ ] Measured shared foreign-wide GB/day quotas (combined Maya1 + Maya3) and capacity reservations.
- [ ] Iran-edge-specific IP block: one gateway quarantines F1 without removing F1 for the other.
- [ ] F1 loss: remaining routes function; F2 service and x-ui PID unchanged.
- [ ] F2 loss: F1 functions; cross-gateway F3/F4 reserve if provisioned and capacity allows.
- [ ] F3 / F4 failures mirror the above on Maya3.
- [ ] Simultaneous both primaries lost: deliberate capacity-bound emergency failover; no unapproved direct bypass.
- [ ] One gateway unavailable while replacing F1: UI shows INCOMPLETE and cannot delete old F1.
- [ ] Controller dies: existing data sessions unaffected, mutation blocked until safe reconciliation.
- [ ] Probe overhead and periodic log volume measured/limited.

## Gate E — user experience / rollout
- [ ] Existing x-ui 2.9.4/REALITY inbound, subscriptions and all client configs preserved.
- [ ] Pilot with isolated users, real Telegram (chat and calls), YouTube, browsing, QUIC fallback testing, persistent TCP and large transfers.
- [ ] Minimum 24-hour burn-in and realistic peak 290-user / ~500GB/day traffic simulation.
- [ ] Failover time, setup latency, reconnect success, packet retransmissions and CPU/Memory baseline recorded.
- [ ] One-step rollback demonstrated for each migration step.
- [ ] Owner explicitly authorizes scheduled production cutover.

## Definition of done
Green unit tests **alone are insufficient**. No security downgrade is an acceptable workaround.
