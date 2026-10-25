# Stage 2 — Independent F2 XHTTP + REALITY TCP laboratory

**LAB ONLY; NOT PRODUCTION, not yet installed/tested on physical F2 or Maya1.**
F1 Naive remains untouched. The new F2 is the second of the four allowed foreign
servers (F1–F4), NOT a fifth machine. No Cloudflare, Bridge, CDN, remote UDP,
public SOCKS, x-ui routing changes, or customer config changes.

Design based on XTLS/Xray-examples
`VLESS-XHTTP-Reality/minimal-steal_others`.
One XHTTP `stream-one` REALITY tunnel over TCP; login/key/path created
out-of-band and pinned to a single F2. Client port `127.0.0.1:17996`.

## Prerequisites

- **New dedicated F2 foreign**: fresh Ubuntu x86_64, public IPv4,
  TCP/443 available, provider firewall inbound TCP/443 allowed.
- Foreign must reach public TLS1.3 + HTTP/2 camouflage target (e.g.
  `www.microsoft.com`). The installer validates it. The camouflage
  name is a TLS handshake impersonation name, not a reverse proxy or CDN.
- **Maya1 Iran**: existing x-ui v2.9.4 and proven F1 Naive lab,
  no active customer migration, stage0 role `maya1`.
- Independent authenticated SSH access from Maya1 to F2; verify SSH host
  key using VPS provider console. NEVER disable StrictHostKeyChecking.
- Re-check live available RAM and VMware Ballooning after Maya1 rebuild before any testing. This lab remains for small smoke tests only.

## 1. Deploy NEW F2 foreign

On the F2 foreign ONLY:

```bash
sudo apt-get update
sudo apt-get install -y git python3
sudo git clone --depth 1 https://github.com/aliiitavazoeiii-afk/mega-tunnel.git /opt/mega-tunnel
cd /opt/mega-tunnel
sudo bash ops/bootstrap-stage0.sh f2
sudo bash ops/install-xhttp-lab-foreign.sh f2
```

Enter its public IPv4 and a real external TLS1.3+H2 hostname as REALITY
camouflage target. Do not enter the F1 foreign IP. No DNS record is
required for the F2 endpoint because authorized REALITY clients dial F2's
IP directly using the camouflage `serverName`.

Pinned version: Xray `v26.9.30`, whose ZIP SHA256 is verified before
install. The installer creates its own x25519 keypair, UUID, short ID
and XHTTP path, tests `xray run -test`, installs the separate nonroot
systemd unit `mega-f2-xhttp-foreign.service`, and leaves private bundle:

`/root/mega-f2-xhttp-client.json`.

The copied executable for Maya1 is
`/usr/local/lib/mega-tunnel/xray-v26.9.30`. Do not paste the bundle,
server JSON, private key, or path into a chat.

## 2. Copy F2 files securely to MAYA1 Iran

Get F2_IPV4 from your VPS provider and verify SSH fingerprint through
their out-of-band console. On Maya1:

```bash
ssh root@F2_IPV4
# Verify host key against provider console, then exit.
sudo scp -o StrictHostKeyChecking=yes \
 root@F2_IPV4:/root/mega-f2-xhttp-client.json /root/mega-f2-xhttp-client.json
sudo scp -o StrictHostKeyChecking=yes \
 root@F2_IPV4:/usr/local/lib/mega-tunnel/xray-v26.9.30 /root/mega-f2-xray-bin
sudo chmod 0600 /root/mega-f2-xhttp-client.json /root/mega-f2-xray-bin
```

Both files are cross-checked: the binary digest must match the hash
included in the private F2 bundle created from the verified ZIP.

## 3. Install isolated XHTTP client on MAYA1

```bash
cd /opt/mega-tunnel
sudo git pull --ff-only
sudo bash ops/install-xhttp-lab-iran.sh maya1 \
 /root/mega-f2-xhttp-client.json /root/mega-f2-xray-bin
```

This does NOT apt-get on Maya1, restart x-ui, change its inbound, or touch
F1. The local service is `mega-f2-xhttp-client` with loopback SOCKS
`127.0.0.1:17996`, independent of Naive F1 `127.0.0.1:17995`.

Expected installer success: >=4 of 5 HTTPS 204 requests, no restart.

## 4. Verify independent routes

On Maya1:

```bash
sudo bash /opt/mega-tunnel/ops/test-two-paths-maya1.sh
```

It checks each path **sequentially with only five light requests**, so
this does NOT prove concurrency, app QoE, production traffic, masking
traffic volume, long-lived sessions or failover.

If F2 fails, DO NOT overwrite the config, re-run the original installer,
or change x-ui. Check only:

```bash
sudo systemctl show mega-f2-xhttp-client \
 -p ActiveState -p NRestarts -p ExecMainStatus -p MemoryCurrent
sudo ss -ltn '( sport = :17996 )'
```

Foreign F2:

```bash
sudo systemctl show mega-f2-xhttp-foreign \
 -p ActiveState -p NRestarts -p ExecMainStatus -p MemoryCurrent
sudo ss -ltn '( sport = :443 )'
```

Keep private server-side Xray logs and configs private until redacted.

## Next stages NOT implemented

- x-ui 2.9.4 outbound attachment and routed canary
- REALITY/XHTTP auto-failover or weighted traffic sharing
- TLS fingerprint/anti-filter field validation
- cross-gateway emergency F3/F4 access
- authenticated controller, signing, replacement dashboard
- UDP app compatibility or 290-user/500GB/day performance tests

Do not connect paying customers to this standalone lab.
