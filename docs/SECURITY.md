# Threat model and no-downgrade contract

## Actors / threats
Network censor with DPI and destination-IP blocking, malicious Internet scanner, stolen node credentials, compromised foreign VM, compromised dashboard session, controller partition and accidental operator mistakes.

## Guarantees that are feasible
- Strong authenticated, encrypted server-to-server transport; independent NaiveProxy/TLS and XHTTP/REALITY pathways.
- Protect administrative plane by mTLS + firewall/VPN administrative overlay and short-lived device certificates.
- Immutable versioned foreign inventory; foreign replacement has dry-run, dual-gateway approval, auditable apply and rollback.
- Provenance-pinned installer, binary/checksum signature verification, non-root services, systemd limits, least privilege.
- Protect client data, avoid logging PII/IPs by default, never store admin secrets on GitHub or in shell history.

## Non-guarantees
- **No design makes 500 GB/day invisible to an on-path observer.** Bytes, IPs, session timing and packet rates are observable even with TLS.
- A direct Iran-to-foreign tunnel reveals the direct foreign destination IP (no Cloudflare or Bridge in this version).
- Blocking a path can kill existing sockets. Only newly established sockets can be reassigned normally.
- TCP-only foreign transport may not satisfy every app's UDP/real-time behavior without a distinct tested compatibility mechanism.

## Security release blockers
1. No unauthenticated control API exposed beyond localhost; production must have device mTLS and operator SSO/MFA.
2. Secrets cannot appear in URLs, logs, process arguments, Git commits, install commands, dashboard HTML or browser localStorage.
3. API rejects generation replay, unknown actors, unauthorized roles, CSRF, and a stale/wrong gateway.
4. Installer refuses unpinned/unverified downloads and never runs arbitrary `curl | bash` from moving `main`.
5. Signed desired state, controller fencing, dual-gateway convergence and audit logging are verified by integration tests.
6. Replacement cannot silently change transport class, client inbound, subscription hostname or RELAY destination.
7. Failed prep/commit must retain last-known-good path; no global restart or automatic destructive cleanup.
8. Supply chain: pinned toolchains and action revisions, dependency audit, signed release artifacts.
9. Correlated outage drills and load tests passed before production cutover.

When troubleshooting, it is **forbidden** to fix by: disabling TLS verification, opening unauthenticated SOCKS externally, switching to plain HTTP/SSH as an unreviewed fallback, disabling health checks, removing sticky protection without evidence, disabling logging/auditing, or bypassing the two-node synchronization contract.
