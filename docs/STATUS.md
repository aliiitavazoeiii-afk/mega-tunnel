# Implementation status — 2026-10-24

**NOT PRODUCTION READY. DO NOT DEPLOY ON LIVE MAYA1/MAYA3.** No live VPN servers were modified.

## Implemented and committed
- 30 fixed product requirements and anti-downgrade security/operational contract.
- Architecture: Maya1/Maya3, four logical foreign nodes, each gateway's two primaries and cross-gateway emergency access.
- Dependency-free per-flow **decision** engine: capacity-aware primary selection, per-edge quarantine filtering, sticky route guard, stale-global-byte checks.
- HEALTHY/SUSPECT/QUARANTINED/PROBATION deterministic edge circuit domain model.
- Versioned replacement **domain** workflow with dual gateway PREPARE + APPLY acknowledgements, old foreign retention, guarded canary/drain and optionally preapproved automatic cleanup **eligibility** after grace window. No remote execution and no deletion has been implemented.
- Loopback-only, explicitly laboratory SOCKS5 TCP forwarder `mega_tunnel/lab_proxy.py`: local SOCKS transport adapters only, CONNECT only, no direct fallback, no x-ui edits.
- Static Persian RTL dashboard UX preview `dashboard/index.html`. Destructive controls disabled.
- `ops/preflight-iran.sh`, `ops/preflight-foreign.sh` (read-only), `ops/diagnose-tcp.py` (IP-redacted, read-only).
- Github Actions unit and syntax tests; latest run URL visible under Actions.
- Detailed acceptance, security, dashboard, installation, operations and phased delivery docs.
- Ten tracked GitHub issues for release work and observed Maya1 performance bottlenecks.

## NOT IMPLEMENTED — release blockers
- Pinned and tested real NaiveProxy and Xray XHTTP/REALITY foreign/client transport pairs.
- A supported production data plane with UDP app compatibility and 290-user load test.
- Durable multi-node signed controller with mTLS-agents, monotonic persisted generations, leader fencing and transaction audit.
- A secure, live dashboard connected to real gateways with SSO/MFA, CSRF and RBAC.
- A signature/digest verified single-command foreign installer with short-lived enrollment, production daemon and rollback.
- Actual two-Maya coordinated foreign replacement and old-node teardown.
- The x-ui **2.9.4** adapter preserving REALITY public 443, Xray API routing, user stats, subscriptions and runtime version checks.
- Automated canary/staged migration with pilot results, disaster recovery, memory/CPU/TCP performance regression and QoE acceptance.
- Supply-chain release signing and signed desired-state end-to-end audit.

## Safety
Tests passing is NOT proof of working VPN or DPI resistance. Direct foreign IP, volume and timing remain visible on path. No guarantee of seamless handoff for already-open TCP sessions. No immediate destructive foreign deletion after a health probe.
