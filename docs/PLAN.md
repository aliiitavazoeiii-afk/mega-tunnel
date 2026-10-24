# Phased implementation plan — do not skip hard parts

Phase 0 (source complete): security/reliability invariants, models, test harness, prototype UX, CI.

Phase 1 (network lab): install pinned NaiveProxy and XHTTP-REALITY TCP-only paths on non-production nodes; verify kernel compatibility, certificates, protocol fingerprints and live app behavior, per-path traffic counters. DO NOT edit x-ui yet.

Phase 2 (data plane): implement Go-based bounded-connection local SOCKS/HTTP forwarder with route decision RPC snapshot, per-flow stickiness, isolated transports, graceful draining, sub-second local circuit decisions from passive signals, global-rate and per-node quotas. Load test against four synthetic foreign endpoints.

Phase 3 (control plane): transactional PostgreSQL, controller epochs, signed desired-state snapshots, certificate identities, controller/agent mTLS, reconcile/split brain, complete audit / RBAC / MFA. Agent configuration validation and atomic versioned updates.

Phase 4 (foreign installer): signed release artifacts pinned to SHA256 and signature, single use enrollment, Linux systemd non-root and firewall, secure bootstrap read from stdin. Foreign agent installs transport and reports health/version; no secrets on command line or Github.

Phase 5 (dashboard): real signed-in Persian UI wired to controller; guided replacement wizard including two gateway ACKs, canary, drain and rollback. Never rely on static mock.

Phase 6 (realistic exercise): failure inject each foreign, each Iran edge and both primaries; packet loss/jitter, CPU pressure, blocked domain, stale metrics and controller partition. Telegram/YouTube/long-lived session tests. Pass all gates in docs/ACCEPTANCE.md.

Phase 7 (production): canary on isolated test subscription with no original inbound edits; incremental cutover; compare QoE and retain rollback; only with operator approval. No forced upgrade or shutdown of old frp-tunnel.

Alternative architectures (five direct foreign, Cloudflare/Bridge and SSH Bridge) are deferred and explicitly OUT OF SCOPE for budget V1, not silently introduced as fixes.
