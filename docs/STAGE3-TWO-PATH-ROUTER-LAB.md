# Stage 3: Maya1 local dual-carrier router LAB

**NOT PRODUCTION.** The already field-verified carrier paths are:

- Maya1 -> F1: Naive TCP, local `127.0.0.1:17995` (5/5 HTTP 204)
- Maya1 -> F2: XHTTP+REALITY TCP, local `127.0.0.1:17996` (5/5 HTTP 204)

Field state as of 2026-10-25: F1 and F2 `ActiveState=active`,
zero service restarts; Maya1 available RAM approx 1.5GiB, VMware
balloon 0 MB; x-ui v2.9.4 active but routing not configured for Mega.

## New LAB TCP entrypoint

`127.0.0.1:17990` -> loopback F1 or F2 SOCKS adapter.
Router never dials the public Internet directly. It does not configure,
restart or alter x-ui, its public inbound, customer UUIDs, or any
foreign servers. SOCKS UDP ASSOCIATE is explicitly rejected.

A targeted low-noise check every 45 seconds makes a real SOCKS CONNECT
through each individual carrier to `www.gstatic.com:443`, performs TLS
certificate verification (no skip), and reads HTTP 204. This identifies
a broken end-to-end route better than checking whether localhost SOCKS
accepts TCP. A failed probe moves an edge into SUSPECT and prevents new
flows from picking it. Repeated failures quarantine; recovery requires
cooldown plus verified successes. Stale probe data rejects routes.
Never automatically restart a transport just because one health check
fails.

An upstream SOCKS CONNECT failure can be retried via the other healthy
adapter *before reporting success to the client*. Established TCP streams
cannot migrate mid-connection and must reconnect on an outage. Probe
target restrictions, remote reachability, cold start, and occasional
false negative results still need field validation.

**This is NOT a production weighted balancer.** The current route
scoring uses local observed lab flow bytes and a reference inventory.
It does not yet have authoritative daily totals from both Maya gateways,
actual egress GB/day quotas, per-app QoE telemetry, signed controller
snapshots, user UDP support or x-ui integration.

## Install (Maya1 IRAN ONLY)

Do not run on foreign F1/F2 and do not run on Maya3.

```bash
cd /opt/mega-tunnel
sudo git pull --ff-only
sudo bash ops/install-two-path-router-lab.sh maya1
```

Requires both local carrier services active, x-ui installed as v2.9.4,
correct `/etc/mega-tunnel/stage0.json` role Maya1 and localhost
port 17990 unoccupied. It refuses to overwrite an existing router lab.

Service: `mega-maya1-router-lab.service`.

## Test through the real routed lab entrypoint

```bash
cd /opt/mega-tunnel
sudo bash ops/test-two-path-router-lab.sh
```

Expected at least 8/10 `HTTP 204` through the local router. The test
also reads F1/F2/x-ui service activity and memory use. For a failure:

```bash
systemctl show mega-maya1-router-lab \
  -p ActiveState -p NRestarts -p ExecMainStatus -p MemoryCurrent
journalctl -u mega-maya1-router-lab -n 40 --no-pager
ss -ltn '( sport = :17990 )'
```

Only include safe journal lines; do not share private foreign bundle,
panel database, config credentials or customer identifiers.

## Safe uninstall (router LAB ONLY)

```bash
sudo systemctl disable --now mega-maya1-router-lab
```

This turns off ONLY the lab entrypoint; leaves F1, F2 and x-ui
untouched. Retain its config for investigation. Do not remove shared
Mega Tunnel parents or foreign/node configs.

## Release blockers

No paying users should be sent to the router lab. Before production:
repair / audit x-ui `xrayTemplateConfig` and inbound rules, implement
tested version-pinned x-ui 2.9.4 adapter and isolated canary; implement
authoritative daily counters, byte budgets, capacity limits,
passive/active telemetry, realistic load testing, and failure injection.
The startup behavior and health-probe calibration also need field data.
