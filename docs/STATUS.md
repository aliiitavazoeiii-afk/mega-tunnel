# Implementation status — 2026-10-24

**NOT PRODUCTION READY.** Stage1 only has an isolated loopback Naive SOCKS lab on Maya1 and a tested separate F1 foreign; x-ui user routes have NOT been modified. Stage2 F2 XHTTP REALITY is source-only, NOT deployed or field-tested.

## 2026-10-25 — Stage 1 Naive TCP lab (code ready; NOT deployed)

- Added `ops/install-naive-lab-foreign.sh` for a real pinned Naive HTTPS TCP foreign lab F1 or F3, with Caddy Naive TLS and a private bundle.
- Added `ops/install-naive-lab-iran.sh` for a real encrypted client through the foreign, bound to loopback TCP SOCKS at 17995 for Maya1 (17997 for Maya3). x-ui **2.9.4** is checked but NEVER altered.
- Added `ops/test-naive-lab.sh` for sequential HTTPS smoke/latency tests and host RAM observation.
- Official upstream binary versions and digests are pinned and validated, and shell syntax checks are included in CI.
- Instructions: `docs/STAGE1-NAIVE-LAB.md`. **Actual F1 and Maya1 field tests now passed (9/10 HTTPS-204, example.com 200, Telegram HTTP 302).** One startup timeout was observed. No x-ui routed traffic was changed.
- On Maya1 the VMware balloon consumed approximately **1,278 MB of its nominal 2 GB**; the hosting provider was contacted. Do not run concurrency/load tests before the provider resolves balloon pressure.

## 2026-10-25 — Stage2 F2 XHTTP + REALITY pilot (SOURCE READY, NOT DEPLOYED)

- Official Xray examples for VLESS XHTTP + REALITY inspected; TCP-only `stream-one` experimental configuration constructed for separate F2 (Maya1) / F4 (Maya3).
- `ops/install-xhttp-lab-foreign.sh`: dedicated F2/F4 non-root Xray listener, upstream ZIP v26.9.8 pinned SHA256, generated per-lab REALITY X25519 keys, credentials and protected private F2 bundle.
- `ops/install-xhttp-lab-iran.sh`: install from securely copied, hash-matched foreign binary and private bundle (no internet downloads/apt on memory-constrained Maya1), bind loopback SOCKS at 17996 for F2 or 17998 for F4, keep x-ui and Naive F1 untouched.
- `ops/test-two-paths-maya1.sh`: lightweight sequential 5-request per-carrier smoke tests.
- `docs/STAGE2-XHTTP-LAB.md`: exact manual install, security and acceptance limits.
- **No physical F2 setup or Maya1 F2 TCP result has been observed.** GitHub Actions green = syntax/test guards only, NOT a verified connection.
- Maya1 VMware Memory Balloon remains `1278 MB`, so no capacity stress tests or customer routing.

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
- **Production**-hardened and load-tested NaiveProxy and Xray XHTTP/REALITY foreign/client transport pairs (F1 lab passed light TCP checks; F2 is source-only).
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
