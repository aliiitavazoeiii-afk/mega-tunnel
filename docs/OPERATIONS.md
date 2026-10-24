# Operations runbook (DESIGN — commands here are not live yet)

## Safe foreign replacement: example F1

1. In secured dashboard choose F1; inspect primary Maya1 usage AND emergency Maya3 dependency.
2. Press 'Replace' and receive *impact preview*: old endpoint, assigned transports, live flows, quota, both edges' health, generation.
3. Enter new server address via authenticated UI; address must never enter the Git repository. The UI issues a one-use limited-time bootstrap enrollment.
4. System presents **one pinned installer command** for the new foreign. The command must verify a signed release digest and use the one-time token via protected stdin / secure enrollment exchange, never in shell argv/history.
5. New node installs an unprivileged agent and chosen transport. Existing foreign is left running. Installer validates version, TCP listeners, TLS identity, kernel/network budget and egress.
6. Controller probes new foreign **independently from Maya1 and Maya3**, and requires explicit verification of both compatible transport and observed application path. If either fails, replacement stays pending.
7. Both agents PREPARE a signed higher generation (config parse, sidecar reserve, connectivity and dry-run). No live routing change yet.
8. Controller issues COMMIT only when both PREPARE. Agents change policy for *new* flows using atomic generation swap, and provide verifiable ACK.
9. If one fails, UI shows PARTIAL + remediation; old node stays safe. Reconcile with fencing and replay-safe generations. No blind failover to insecure/default transport.
10. Run 1% → 10% → 25% → 50% → 100% traffic ramp only if app metrics and capacity hold. Move old active flows only through natural close or scheduled maintenance.
11. After explicit 'drained and safe' + operator cleanup confirmation, decommission old foreign. Never automatically delete old server.
12. Record audit ID, timestamps, two ACKs, health samples, new digest, optional rollback generation. Show operation success only at this point.

### Rollback
Use a signed prior generation validated against both gateways, tested old foreign and spare capacity; restore new-flow policy while active flows drain. A controller failure must not undo healthy running data plane.

### Standard incident modes
- One (gateway, foreign) edge inaccessible: quarantine only that edge.
- One foreign globally unreachable: both edges quarantine, quota redistributed within limits.
- High CPU/memory on one gateway: shed high-cost new flows within policy, never mass restart.
- Unknown DPI behavior: log confidence and samples; no unsupported promise of hidden bytes.
- Partial split-brain / controller offline: freeze foreign replacement, operate signed last-known-good.
- Both primaries unavailable: eligible emergency cross routes only if metrics fresh, verified healthy, with spare capacity; otherwise honest outage.
- Client UDP issues: separately disable unsupported app features or supply a tested UDP-over-TCP compatibility layer in future, never claim no degradation.

## Observability screens
Overview: both Iran gateways and combined totals. Foreigns: logical IDs and statuses per gateway, today/30d bytes, sessions, errors, RTT, capacity, current candidate. Incidents: timeline of transitions and recovery, evidence. Replacement: wizard, two ACK timeline, rollback, old-drain. Security: session list, audit events, cert age, build version. Never render credentials.

## Remote deployment policy
This repository does not yet ship live installers, agents or dashboard APIs. Do not copy experimental CLI into live systemd; complete release gates first.
