# Stage 1 — REAL Naive TCP laboratory: Maya1 ↔ F1 (or Maya3 ↔ F3)

This is a functional TCP encrypted foreign transport test, **not** the completed Mega Tunnel. There is no XHTTP, no UDP/XUDP, no cross-gateway failover, no signed controller, no protected dashboard, no x-ui routing modification. The server-to-server observable foreign IP/byte pattern is NOT hidden from the network.

## Prerequisites

- Foreign: a fresh Ubuntu x86_64 VPS with its own public global IPv4, ports TCP 443 and 80 available at provider firewall (HTTP-01 challenge when used), a unique DNS-only A hostname pointing at that VPS, and a contact email for TLS.
- Iran Maya1: x-ui **exactly 2.9.4**, no customers currently using the gateway, enough temporary RAM for ~100–200 MiB more, and root SSH access to foreign. VMware ballooning currently ~1278 MB on a 2 GB machine, so **NO high-concurrency or load tests** until provider fixes the host allocation.
- Browser/public clients: unchanged; this PoC binds local SOCKS only.

## Foreign F1: install and obtain secure bundle

On the **new F1 foreign**:

```bash
apt-get update && apt-get install -y git python3
git clone --depth 1 https://github.com/aliiitavazoeiii-afk/mega-tunnel.git /opt/mega-tunnel
cd /opt/mega-tunnel
sudo bash ops/bootstrap-stage0.sh f1
sudo bash ops/install-naive-lab-foreign.sh f1
```

Enter **new foreign public IPv4**, **new DNS-only hostname** and Let's Encrypt contact email. The installer downloads **pinned** Caddy with SHA256 verification; installs a non-login service user and a restricted, self-contained systemd service; validates TLS certificate issuance; creates private `/root/mega-f1-naive-client.json` with permissions 0600. Do NOT share the bundle in chat or GitHub. The service is `mega-f1-naive-foreign.service`.

## Iran Maya1: secure transfer and install local client

First verify the foreign's SSH host fingerprint using the VPS provider console, then trust it through a legitimate first SSH connection. Never disable SSH host-key checking. On **Maya1 Iran**:

```bash
apt-get update && apt-get install -y git python3
git clone --depth 1 https://github.com/aliiitavazoeiii-afk/mega-tunnel.git /opt/mega-tunnel
cd /opt/mega-tunnel
sudo bash ops/bootstrap-stage0.sh maya1
sudo ssh root@NEW_FOREIGN_IPV4
# exit after verifying and accepting SSH host key from provider console
sudo scp -o StrictHostKeyChecking=yes \
  root@NEW_FOREIGN_IPV4:/root/mega-f1-naive-client.json /root/mega-f1-naive-client.json
sudo chmod 600 /root/mega-f1-naive-client.json
sudo bash ops/install-naive-lab-iran.sh maya1 /root/mega-f1-naive-client.json
sudo bash ops/test-naive-lab.sh maya1
```

The Iran local service is `mega-f1-naive-client.service` with SOCKS5 TCP on `127.0.0.1:17995`; **no x-ui changes or public VPN inbound restarts**. The installer validates actual 204 HTTPS via the foreign.

## Diagnostics

```bash
sudo systemctl status mega-f1-naive-foreign --no-pager
sudo journalctl -u mega-f1-naive-foreign -n 30 --no-pager
```

Run those only on the foreign.

```bash
sudo systemctl status mega-f1-naive-client --no-pager
sudo journalctl -u mega-f1-naive-client -n 30 --no-pager
sudo bash ops/test-naive-lab.sh maya1
free -h
vmware-toolbox-cmd stat balloon
```

Run those only on Maya1. Do not paste private bundle/client JSON or full Caddyfile into chat or logs.

## Important

- Rebuilding an idle gateway does not automatically validate the new data path under actual client workload.
- Real TCP data flows through the encrypted Naive tunnel, but **UDP support, XHTTP F2, router quotas, and foreign replacement are unimplemented** in this stage.
- The installers intentionally reject re-installing an existing role; do not remove configs to force rerun.
- Foreign endpoints are direct IP destinations visible to an on-path observer. Do not promise anti-DPI volume invisibility.
- If the certificate issuance or validation fails, **stop**. Do not disable TLS verification, use plaintext proxy, skip checksum, or attach x-ui.
- After F1 smoke tests succeed, provision F2/XHTTP independently and exercise per-flow selection under bounded load only after memory pressure is resolved.
