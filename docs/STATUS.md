# Implementation status — 2026-10-24

## DONE
- Repo initialized with explicit product requirements, security no-downgrade policy, architecture, dashboard UX, acceptance gates.
- Dependency-free first-pass routing, health and replacement coordination **domain logic**, plus deterministic offline tests (see source).
- Public GitHub repository contains only example/test data, **no production secrets**.

## NOT DONE — DO NOT DEPLOY TO PRODUCTION
- Working NaiveProxy and Xray XHTTP/REALITY foreign/client transport provisioning.
- Real encrypted gateway-to-controller mTLS agents, transactional persistent control plane, distributed generation ACK and reconciliation.
- Production router SOCKS data-path implementation; mock chooser is **not** a network forwarding engine.
- Authenticated production dashboard with full replacement wizard, RBAC/MFA and real server status.
- Hardened one-command, signed foreign installer / enrollment / credential rotation.
- Dual x-ui 2.9.4 integration, rollback and no-user-config-change verification.
- Real rate meters/quotas from both Iranian servers; cross-capacity arbitration with partitions.
- Sustained ~290 user / 500 GB/day load test, Telegram/YouTube testing and failover injection.
- Release signing, supply chain scan, independent threat-model review, staged migration.

No live Maya1/Maya3 machine has been touched. All changes here are repository code and documentation only. A passing unit test is NOT a production readiness claim.
