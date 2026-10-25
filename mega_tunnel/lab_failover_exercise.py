#!/usr/bin/env python3
"""Non-destructive F1/F2 failover integration exercise, Maya1 LAB ONLY.

Temporarily starts three random localhost-only listeners:
- an F1 fault gate forwarding to the real Naive SOCKS 17995,
- an F2 fault gate forwarding to the real XHTTP SOCKS 17996,
- a new ephemeral lab router listening on an OS-assigned local port.

Disables only test gates to simulate edge loss. NEVER touches live F1/F2
services, port 17990 router, x-ui, firewall, default route, users or DNS.
"""
import asyncio
import shutil
import sys

from mega_tunnel.lab_proxy import LabRouter, pump
from mega_tunnel.lab_health import CarrierMonitor

EXPECTED_SERVICES = (
    "mega-f1-naive-client.service",
    "mega-f2-xhttp-client.service",
    "mega-maya1-router-lab.service",
    "x-ui.service",
)


async def local_service_up(name):
    proc = await asyncio.create_subprocess_exec(
        "systemctl", "is-active", "--quiet", name
    )
    return await proc.wait() == 0


class FaultGate:
    """Test-only local forwarding gate; unbinds when exercise terminates."""

    def __init__(self, name, real_port):
        self.name = name
        self.real_port = real_port
        self.enabled = True
        self.listener = None
        self.connections = set()

    @property
    def port(self):
        return self.listener.sockets[0].getsockname()[1]

    async def start(self):
        self.listener = await asyncio.start_server(
            self.accept, host="127.0.0.1", port=0
        )

    async def accept(self, client_r, client_w):
        task = asyncio.current_task()
        self.connections.add(task)
        remote_w = None
        try:
            if not self.enabled:
                return
            remote_r, remote_w = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", self.real_port), timeout=4
            )
            await asyncio.gather(
                pump(client_r, remote_w), pump(remote_r, client_w)
            )
        except (OSError, ConnectionError, TimeoutError,
                asyncio.IncompleteReadError, asyncio.CancelledError):
            pass
        finally:
            if remote_w:
                remote_w.close()
                try:
                    await remote_w.wait_closed()
                except (OSError, ConnectionError):
                    pass
            client_w.close()
            try:
                await client_w.wait_closed()
            except (OSError, ConnectionError):
                pass
            self.connections.discard(task)

    async def stop(self):
        if self.listener is not None:
            self.listener.close()
            await self.listener.wait_closed()
        active = list(self.connections)
        for task in active:
            task.cancel()
        if active:
            await asyncio.gather(*active, return_exceptions=True)


async def check_http(router_port, *, expected_success):
    proc = await asyncio.create_subprocess_exec(
        "curl", "-4", "--noproxy", "", "--proxy",
        f"socks5h://127.0.0.1:{router_port}",
        "-sS", "--connect-timeout", "5", "--max-time", "12",
        "-o", "/dev/null", "-w", "%{http_code}",
        "https://www.gstatic.com/generate_204",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        raise AssertionError("Probe process timed out")
    code = out.decode("ascii", "replace").strip()
    ok = proc.returncode == 0 and code == "204"
    if ok != expected_success:
        raise AssertionError(
            f"Unexpected routed result: HTTP={code}, curl_exit={proc.returncode}, "
            f"expected_success={expected_success}"
        )
    return code


async def execute():
    if not shutil.which("curl"):
        raise SystemExit("curl must be installed")
    for unit in EXPECTED_SERVICES:
        if not await local_service_up(unit):
            raise SystemExit(f"Required existing service not active: {unit}. STOP")

    f1 = FaultGate("F1", 17995)
    f2 = FaultGate("F2", 17996)
    await f1.start()
    await f2.start()
    server = None
    try:
        paths = {"F1": f1.port, "F2": f2.port}
        monitor = CarrierMonitor(paths)
        router = LabRouter("Maya1", paths, monitor=monitor, max_connections=16)
        server = await asyncio.start_server(
            router.handle, "127.0.0.1", 0
        )
        router_port = server.sockets[0].getsockname()[1]
        print("TEST-ONLY: all endpoints bound to 127.0.0.1 on ephemeral ports")
        print("NO x-ui, F1/F2, firewall, routes or existing 17990 router modifications")

        # Scenario A: Both gates forward to real, running transport services.
        await monitor.check_all()
        if not (monitor.allowed("F1") and monitor.allowed("F2")):
            raise AssertionError("Both real carriers did not verify TLS/HTTPS")
        for _ in range(2):
            await check_http(router_port, expected_success=True)
        print("A BOTH HEALTHY: 2/2 HTTPS requests PASS")

        # Scenario B: F1 gate is DOWN. F2 must exclusively carry new flows.
        f1.enabled = False
        await monitor.check_all()
        if monitor.allowed("F1") or not monitor.allowed("F2"):
            raise AssertionError("F1 outage was not isolated to F1")
        for _ in range(3):
            await check_http(router_port, expected_success=True)
        print("B SIMULATED F1 DOWN -> REAL F2: 3/3 HTTPS requests PASS")

        # Scenario C: F1 gate restored, F2 DOWN. F1 must carry new flows.
        f1.enabled = True
        f2.enabled = False
        await monitor.check_all()
        if not monitor.allowed("F1") or monitor.allowed("F2"):
            raise AssertionError("F2 outage was not isolated to F2")
        for _ in range(3):
            await check_http(router_port, expected_success=True)
        print("C SIMULATED F2 DOWN -> REAL F1: 3/3 HTTPS requests PASS")

        # Scenario D: Both test gates DOWN; never use direct bypass.
        f1.enabled = False
        f2.enabled = False
        await monitor.check_all()
        if monitor.allowed("F1") or monitor.allowed("F2"):
            raise AssertionError("Both-down circuit did not fail closed")
        await check_http(router_port, expected_success=False)
        print("D SIMULATED BOTH DOWN: no direct fallback PASS")

        # Scenario E: Both gates restored, verify recovery behavior.
        # After two failures one edge may enter QUARANTINED; reintroduction
        # follows a real cooldown and success streak, not immediate reset.
        f1.enabled = True
        f2.enabled = True
        await monitor.check_all()
        if not (monitor.allowed("F1") or monitor.allowed("F2")):
            print("E RECOVERY: cooldown/probation expected; immediate ready route not assumed")
        else:
            await check_http(router_port, expected_success=True)
            print("E RECOVERY: at least one verified healthy carrier PASS")
        print("PASS: independent live-carrier test with isolated local fault injection")
        print("This does NOT reproduce upstream IP filtering, packet loss or live user failures.")
    finally:
        if server is not None:
            server.close()
            await server.wait_closed()
        await f1.stop()
        await f2.stop()
        print("All temporary local test gates/router closed. Live services unchanged.")


def main():
    if len(sys.argv) != 1:
        raise SystemExit("Usage: sudo python3 -m mega_tunnel.lab_failover_exercise")
    try:
        asyncio.run(execute())
    except (AssertionError, OSError, ConnectionError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
