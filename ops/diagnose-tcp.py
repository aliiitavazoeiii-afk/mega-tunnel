#!/usr/bin/env python3
"""Read-only, IP-redacted Linux TCP bottleneck probe for Maya1/Maya3.

Runs two 5-second samples; NEVER restarts services, routes traffic or edits x-ui.
This measures the host and local tunnel listeners, not an end-to-end QoE guarantee.
"""
import argparse
import json
import re
import subprocess
import time
from pathlib import Path

PORTS = (443, 7990, 7991, 7992, 7993, 7994)
KEYS = {
    ("Tcp", "OutSegs"), ("Tcp", "RetransSegs"),
    ("Tcp", "EstabResets"), ("TcpExt", "TCPTimeouts"),
    ("TcpExt", "ListenDrops"), ("TcpExt", "ListenOverflows"),
    ("TcpExt", "TCPBacklogDrop"), ("TcpExt", "TCPSynRetrans"),
}


def read_netstats():
    result = {}
    for path in ("/proc/net/snmp", "/proc/net/netstat"):
        try:
            lines = Path(path).read_text().splitlines()
        except OSError:
            continue
        for a, b in zip(lines, lines[1:]):
            h, v = a.split(), b.split()
            if not h or not v or h[0] != v[0]:
                continue
            group = h[0].rstrip(":")
            for name, val in zip(h[1:], v[1:]):
                if (group, name) in KEYS:
                    try:
                        result[f"{group}.{name}"] = int(val)
                    except ValueError:
                        pass
    return result


def read_cpu():
    out = {}
    for line in Path("/proc/stat").read_text().splitlines():
        f = line.split()
        if not f or not re.fullmatch(r"cpu\d*", f[0]):
            continue
        x = [int(v) for v in f[1:]]
        out[f[0]] = (sum(x), x[3]+x[4], x[6] if len(x)>6 else 0,
                     x[7] if len(x)>7 else 0)
    return out


def pressures():
    out = {}
    for label in ("cpu", "memory", "io"):
        try:
            s = (Path("/proc/pressure")/label).read_text().splitlines()[0]
            v = re.search(r"avg10=([\d.]+)", s)
            if v:
                out[label] = float(v.group(1))
        except (OSError, IndexError):
            pass
    return out


def linkstats():
    out = {}
    for item in Path("/sys/class/net").iterdir():
        if item.name == "lo" or not (item/"statistics").is_dir():
            continue
        d = {}
        for k in ("rx_dropped", "tx_dropped", "rx_errors", "tx_errors"):
            try:
                d[k] = int((item/"statistics"/k).read_text())
            except (ValueError, OSError):
                pass
        out[item.name] = d
    return out


def socks_for_port(port):
    r = subprocess.run(
        ["ss", "-Htin", "state", "established",
         "(", "sport", "=", f":{port}", ")"],
        capture_output=True, text=True, timeout=12
    )
    if r.returncode != 0:
        return {"error": "ss exit status " + str(r.returncode)}
    count, rx, tx, pending, max_tx, rtt_sum, rtt_count, retrans = (0,0,0,0,0,0.,0,0)
    for line in r.stdout.splitlines():
        f = line.split()
        if not f:
            continue
        offset = 1 if f[0] == "ESTAB" else 0
        if len(f) >= offset+4 and f[offset].isdigit() and f[offset+1].isdigit():
            rq, sq = int(f[offset]), int(f[offset+1])
            count += 1
            rx += rq
            tx += sq
            max_tx = max(max_tx, sq)
            pending += sq > 0
        m = re.search(r"(?:^|\s)rtt:([\d.]+)", line)
        if m:
            rtt_sum += float(m.group(1))
            rtt_count += 1
        m = re.search(r"(?:^|\s)retrans:(\d+)/(\d+)", line)
        if m and int(m.group(1)) > 0:
            retrans += 1
    return {
        "established": count,
        "recvq_bytes": rx, "sendq_bytes": tx, "max_sendq_bytes": max_tx,
        "sockets_with_sendq": pending,
        "sockets_with_pending_retrans": retrans,
        "mean_kernel_rtt_ms": round(rtt_sum / rtt_count, 1) if rtt_count else None,
    }


def delta(a,b):
    return {key: value - a.get(key, value) for key, value in b.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--interval", type=float, default=5.0)
    opts = ap.parse_args()
    if not 1 <= opts.interval <= 30:
        ap.error("interval must be between 1 and 30 seconds")
    before = (read_netstats(), read_cpu(), linkstats())
    time.sleep(opts.interval)
    after = (read_netstats(), read_cpu(), linkstats())
    cpu = {}
    for core, v in after[1].items():
        if core not in before[1]:
            continue
        b = before[1][core]
        total = v[0] - b[0]
        if total <= 0:
            continue
        cpu[core] = {
            "busy_pct": round(100*(1-(v[1]-b[1])/total),1),
            "softirq_pct": round(100*(v[2]-b[2])/total,1),
            "steal_pct": round(100*(v[3]-b[3])/total,1)
        }
    link = {}
    for name, stats in after[2].items():
        link[name] = delta(before[2].get(name, {}),stats)
    report = {
        "mode": "READ_ONLY_NO_ENDPOINT_IPS",
        "sample_seconds": opts.interval,
        "cpu": cpu,
        "pressure_10s_pct": pressures(),
        "tcp_kernel_counter_delta": delta(before[0],after[0]),
        "interface_counter_delta": link,
        "listeners": {str(p): socks_for_port(p) for p in PORTS}
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
