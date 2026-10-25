# Implementation status — 2026-10-24

**NOT PRODUCTION READY.** Maya1 now has field-verified isolated F1 Naive and F2 XHTTP+REALITY TCP loopback carriers; both independently passed 5/5 HTTPS 204 requests. No paying users routed to Mega; x-ui user configurations remain unchanged. Stage3 local-only router code is ready for Maya1 field trial, not yet deployed or verified on server.

## 2026-10-25 — Stage 1 Naive TCP lab (FIELD-VERIFIED)

- Added `ops/install-naive-lab-foreign.sh` for a real pinned Naive HTTPS TCP foreign lab F1 or F3, with Caddy Naive TLS and a private bundle.
- Added `ops/install-naive-lab-iran.sh` for a real encrypted client through the foreign, bound to loopback TCP SOCKS at 17995 for Maya1 (17997 for Maya3). x-ui **2.9.4** is checked but NEVER altered.
- Added `ops/test-naive-lab.sh` for sequential HTTPS smoke/latency tests and host RAM observation.
- Official upstream binary versions and digests are pinned and validated, and shell syntax checks are included in CI.
- Instructions: `docs/STAGE1-NAIVE-LAB.md`. **Actual F1 and Maya1 field tests now passed (9/10 HTTPS-204, example.com 200, Telegram HTTP 302).** One startup timeout was observed. No x-ui routed traffic was changed.
- After Maya1 rebuild the user verified **0 MB VMware balloon** and approx 1.5 GiB available memory. Avoid actual peak-user loading until separate capacity acceptance.

## 2026-10-25 — Stage2 F2 XHTTP + REALITY pilot (FIELD-VERIFIED)

- Official Xray examples for VLESS XHTTP + REALITY inspected; TCP-only `stream-one` experimental configuration constructed for separate F2 (Maya1) / F4 (Maya3).
- `ops/install-xhttp-lab-foreign.sh`: dedicated F2/F4 non-root Xray listener, upstream ZIP v26.9.8 pinned SHA256, generated per-lab REALITY X25519 keys, credentials and protected private F2 bundle.
- `ops/install-xhttp-lab-iran.sh`: install from securely copied, hash-matched foreign binary and private bundle (no internet downloads/apt on memory-constrained Maya1), bind loopback SOCKS at 17996 for F2 or 17998 for F4, keep x-ui and Naive F1 untouched.
- `ops/test-two-paths-maya1.sh`: lightweight sequential 5-request per-carrier smoke tests.
- `docs/STAGE2-XHTTP-LAB.md`: exact manual install, security and acceptance limits.
- F2 foreign actual Xray v26.9.30 service active on TCP 443 and private bundle verified; Maya1 client XHTTP + REALITY installed and confirmed **5/5 HTTP 204**, zero restarts. Additional two-path checks gave F1=5/5 and F2=5/5. This is isolated flow testing, not application load verification.
- Maya1 VMware balloon 0 MB and 1.5 GiB available after rebuild; do not infer 290-user load capacity.

## 2026-10-25 — Stage3 dual-route lab (SOURCE READY, NOT DEPLOYED)

- Added real end-to-end TLS/HTTPS verified carrier monitor with low-noise probes every 45s, per-carrier circuit state and fail-closed if both inaccessible; simulated tests passed.
- Extended existing `mega_tunnel/lab_proxy.py` to admit only carrier paths with fresh verified health, isolate failed routes on *new* SOCKS CONNECTs and not globally restart transports.
- `ops/install-two-path-router-lab.sh` creates only a loopback `127.0.0.1:17990` unprivileged lab service, never edits x-ui or customer inbounds; `ops/test-two-path-router-lab.sh` tests real HTTP 204 through that local router.
- `docs/STAGE3-TWO-PATH-ROUTER-LAB.md` documents user-run install, test, and safe router-only disable.
- **Field verification on actual Maya1 of the Stage3 combined router is still outstanding.** Controller, global quotas, x-ui adapter, UDP, parallel load and verified real-world failover are NOT implemented.

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
- **Production**-hardened and load-tested NaiveProxy and Xray XHTTP/REALITY foreign/client transport pairs (both passed light live TCP checks only).
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
