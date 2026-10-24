# Installation guide — engineering gate

## Production status

**There is no verified full-production Mega Tunnel installer yet.** Do **not** route real Maya1/Maya3 users into the domain model or UI mock. NaiveProxy + XHTTP/REALITY client/server integration, signed installer, secure controller/mTLS and traffic-engineering load/failover tests remain REQUIRED release blockers. This is a security choice, not an omission we can bypass with an unverified script.

The existing x-ui **v2.9.4** on each Iranian gateway is the owner of all clients, public port 443 and user accounting. The foreign machines carry exit traffic only. Replacing a foreign **must not update client subscription or x-ui users**, and it is explicitly forbidden to restart x-ui as part of a routine foreign swap.

## Safe commands you can run now

**Iran preflight (on EACH Maya1 and Maya3; read-only):**

```bash
git clone https://github.com/aliiitavazoeiii-afk/mega-tunnel.git /opt/mega-tunnel
cd /opt/mega-tunnel
git rev-parse HEAD
sudo bash ops/preflight-iran.sh
python3 -m unittest discover -s tests -v
```

This clones a repository to a NEW directory; it does not install a daemon, touch frp-tunnel, alter firewall or edit x-ui. Verify the reported Git commit SHA before authorizing production changes.

**Foreign preflight (on EACH candidate Foreign F1 through F4; read-only):**

```bash
git clone https://github.com/aliiitavazoeiii-afk/mega-tunnel.git /opt/mega-tunnel
cd /opt/mega-tunnel
git rev-parse HEAD
sudo bash ops/preflight-foreign.sh
```

This command does not provision NaiveProxy, XHTTP/REALITY or the foreign data transport: the signed, one-command installer is tracked under GitHub issue #4.

## Planned final installer workflow, NOT YET RUNNABLE

After signed release and controller security gates:
- Iran: one pinned installer, `--role maya1` / `--role maya3`, detects x-ui 2.9.4, backs up safely, prepares detached local ports, validates real user traffic on canary, and switches user routing only after explicit operator approval.
- Foreign: a version-pinned, signed installer with one-time enrollment token obtained via protected input; automatic non-root service setup, mTLS, preflight and readiness.
- Replacement: dashboard selects F1/F2/F3/F4; enroll new foreign, verify from BOTH gateways, PREPARE/COMMIT same signed config generation, canary new flows, graceful drain old flows, cleanup only after safe rollback window and explicit operator approval.
- Do not delete the old machine immediately on first healthy probe: real TCP sessions are not transferrable.
- Never run automatic changes on live x-ui while controller readiness is UNKNOWN.

## Why x-ui version-specific checks matter

The `xrayTemplateConfig` entry in x-ui v2.9.4 is not a generic proxy file. The future adapter must read and validate the exact existing settings and Xray runtime, preserve API and statistics routes, and make reversible controlled changes. Using a later x-ui template on a pinned older version can break accounting and ingress.

## Operational diagnostics

Read-only scripts above inspect host resources, active services, socket counts, x-ui presence, SQLite readability, foreign port conflicts. They cannot replace real 290-user performance tests.

See `docs/ACCEPTANCE.md` and `docs/OPERATIONS.md` for detailed release gates.
