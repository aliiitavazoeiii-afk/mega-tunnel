#!/usr/bin/env python3
"""Maya1-only, non-disruptive dual-carrier distribution measurement.

Creates an ephemeral loopback-only instance of the existing laboratory
router and sends a small number of verified HTTPS-204 requests through it.
Uses real F1/F2 already-running SOCKS paths without touching their services,
the persistent lab router on 17990, x-ui, firewall, or default routes.

Measured payload byte totals are LOCAL LAB proxies for delivered bytes,
not carrier network wire bytes or both-gateway global quota accounting.
"""
import asyncio
import shutil
import sys
from mega_tunnel.lab_health import CarrierMonitor
from mega_tunnel.lab_proxy import LabRouter

REQUESTS = 16
REQUIRED_SERVICES = (
    "mega-f1-naive-client.service",
    "mega-f2-xhttp-client.service",
    "mega-maya1-router-lab.service",
    "x-ui.service",
)


async def service_active(unit):
    p = await asyncio.create_subprocess_exec(
        "systemctl", "is-active", "--quiet", unit
    )
    return await p.wait() == 0


async def https_request(port):
    cmd = (
        "curl", "-4", "--noproxy", "",
        "--proxy", f"socks5h://127.0.0.1:{port}",
        "-sS", "--connect-timeout", "6", "--max-time", "18",
        "-o", "/dev/null", "-w", "%{http_code}",
        "https://www.gstatic.com/generate_204",
    )
    p = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL
    )
    try:
        data, _ = await asyncio.wait_for(p.communicate(), timeout=20)
    except asyncio.TimeoutError:
        p.kill()
        await p.communicate()
        return False
    return p.returncode == 0 and data.strip() == b"204"


async def main():
    if not shutil.which("curl"):
        raise SystemExit("curl is required for this non-disruptive test")
    for unit in REQUIRED_SERVICES:
        if not await service_active(unit):
            raise SystemExit(f"FAIL CLOSED: existing {unit} is not active")

    transports = {"F1": 17995, "F2": 17996}
    monitor = CarrierMonitor(transports)
    await monitor.check_all()
    if not all(monitor.allowed(name) for name in transports):
        raise SystemExit("FAIL CLOSED: one carrier did not pass real TLS/HTTP check")

    router = LabRouter(
        "Maya1", transports, monitor=monitor, max_connections=16
    )
    listener = await asyncio.start_server(
        router.handle, host="127.0.0.1", port=0
    )
    port = listener.sockets[0].getsockname()[1]
    try:
        print("LAB DISTRIBUTION: ephemeral localhost only, no live service edits",
              flush=True)
        successful = 0
        for attempt in range(1, REQUESTS + 1):
            ok = await https_request(port)
            successful += int(ok)
            print(f"HTTPS request {attempt}/{REQUESTS}: "
                  f"{'204 PASS' if ok else 'FAILED'}", flush=True)
            if not ok:
                break
            await asyncio.sleep(0.1)

        # The router only adds payload byte counts after each TCP flow closes.
        # Never mistake in-flight sessions for completed measured traffic.
        for _ in range(50):
            if sum(router.active[name] for name in transports) == 0:
                break
            await asyncio.sleep(0.1)
        active = {name: router.active[name] for name in transports}
        bytes_by = {name: router.byte_totals[name] for name in transports}
        total_bytes = sum(bytes_by.values())
        print("=== OBSERVED ROUTED TCP PAYLOAD, NOT WIRE EGRESS ===")
        for name in ("F1", "F2"):
            ratio = (100 * bytes_by[name] / total_bytes) if total_bytes else 0
            print(f"{name}: {bytes_by[name]} bytes ({ratio:.1f}%); "
                  f"active={active[name]}")
        if successful < REQUESTS:
            raise AssertionError(
                f"Only {successful}/{REQUESTS} HTTPS probes succeeded"
            )
        if any(active.values()):
            raise AssertionError(
                "Some flows still open; completed-byte stats inconclusive"
            )
        if any(bytes_by[name] == 0 for name in transports):
            raise AssertionError(
                "Only one foreign carried measured TCP payload; "
                "routing balance is NOT verified"
            )
        print("PASS: real TLS/HTTP flows through BOTH independent paths")
        print("NOT PROVEN: 50/50 daily wire bytes, user QoE or production load")
    finally:
        listener.close()
        await listener.wait_closed()
        print("Temporary router closed; existing F1/F2/17990/x-ui unchanged")


if __name__ == "__main__":
    if len(sys.argv) != 1:
        raise SystemExit(
            "Usage: sudo python3 -m mega_tunnel.lab_distribution_exercise"
        )
    try:
        asyncio.run(main())
    except (AssertionError, OSError, ConnectionError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1) from error
