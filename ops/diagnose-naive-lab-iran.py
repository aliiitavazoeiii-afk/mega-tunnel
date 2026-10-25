#!/usr/bin/env python3
"""Read-only F1/F3 connectivity diagnostics. Never displays credentials."""
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

def run(cmd, timeout=20):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, "LANG": "C"})
        return (p.returncode, p.stdout.strip(), p.stderr.strip()[:250])
    except subprocess.TimeoutExpired:
        return (124, "", "Process timed out")

def curl_test(label, flags, url):
    fmt = "http=%{http_code} connect=%{time_connect}s tls=%{time_appconnect}s total=%{time_total}s remote=%{remote_ip}"
    rc, out, err = run(
        ["curl", "-4", "-sS", "--connect-timeout", "5", "--max-time", "12",
         "-o", "/dev/null", "-w", fmt] + flags + [url],
        timeout=16)
    print(f"{label}: curl_exit={rc}, {out}")
    if err:
        print(f"{label}_ERROR: {err.splitlines()[0]}")
    return rc, out

if len(sys.argv) != 2 or sys.argv[1] not in ("maya1", "maya3"):
    raise SystemExit("Usage: sudo python3 ops/diagnose-naive-lab-iran.py maya1|maya3")
gateway = sys.argv[1]
role, port = ("f1", 17995) if gateway == "maya1" else ("f3", 17997)
bundle = Path(f"/root/mega-{role}-naive-client.json")
if not bundle.is_file():
    raise SystemExit(f"Private {role} bundle missing; no changes made")
data = json.loads(bundle.read_text())
if data.get("kind") != "mega-naive-lab" or data.get("foreign_id") != role.upper():
    raise SystemExit("Wrong foreign bundle; no changes made")
domain = data["domain"]
ip = data["public_ip"]
print(f"=== MEGA TUNNEL STAGE1 READ-ONLY {gateway} -> {role.upper()} ===")
print(f"Foreign IP: {ip} | Domain: {domain} | TCP:443")
rc, active, _ = run(["systemctl", "is-active", f"mega-{role}-naive-client.service"])
print(f"Naive local service: {active if active else 'unknown'}")
print("=== 1. DIRECT TCP TO FOREIGN ===")
try:
    with socket.create_connection((ip, 443), timeout=5):
        print("TCP_443: CONNECTED")
except OSError as e:
    print(f"TCP_443: FAILED ({type(e).__name__}: {e})")

print("=== 2. DIRECT HTTPS TO FOREIGN: CERTIFICATE VALIDATION ENABLED ===")
print("Expected response: HTTP 407 for an unauthenticated Naive forward-proxy.")
rc, out = curl_test(
    "DIRECT_TLS",
    ["--noproxy", "*", "--resolve", f"{domain}:443:{ip}"],
    f"https://{domain}/"
)
print("=== 3. LOCAL SOCKS LISTENER ===")
try:
    with socket.create_connection(("127.0.0.1", port), timeout=4):
        print(f"SOCKS_{port}: CONNECTED")
except OSError as e:
    print(f"SOCKS_{port}: FAILED ({type(e).__name__}: {e})")

print("=== 4. END-TO-END VIA LOCAL NAIVE SOCKS ===")
curl_test("SOCKS_204",
          ["--proxy", f"socks5h://127.0.0.1:{port}", "--noproxy", ""],
          "https://www.gstatic.com/generate_204")
curl_test("SOCKS_EXAMPLE",
          ["--proxy", f"socks5h://127.0.0.1:{port}", "--noproxy", ""],
          "https://example.com/")
print("=== SYSTEM RESOURCE STATE ===")
rc, out, _ = run(["systemctl", "show", f"mega-{role}-naive-client.service",
                  "-p", "ActiveState", "-p", "ExecMainStatus", "-p", "NRestarts",
                  "-p", "MemoryCurrent"])
print(out)
rc, out, _ = run(["free", "-h"])
print(out)
print("=== END: no configuration changes, secrets not printed ===")
