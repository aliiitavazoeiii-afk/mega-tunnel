"""Low-noise verified HTTPS-over-carrier probes for the isolated TCP lab.

No x-ui changes, direct egress, background daemon restart, or UDP.
A SOCKS listener being up is NOT evidence that the foreign Internet works.
"""
import asyncio
import ssl
import time
from .health import Circuit
from .models import EdgeState

TARGET = "www.gstatic.com"
PORT = 443
INTERVAL_SECONDS = 45
STALE_AFTER_SECONDS = 150


async def https_204_through_socks(local_port: int) -> bool:
    """Verify REAL target TLS and HTTP over one local encrypted carrier."""
    from .lab_proxy import connect_upstream

    raw = TARGET.encode("ascii")
    request = b"\x05\x01\x00\x03" + bytes((len(raw),)) + raw + PORT.to_bytes(2, "big")
    rr, ww = await connect_upstream(local_port, request)
    try:
        # TLS certificate validation (no -k, no insecure fallback).
        context = ssl.create_default_context()
        await ww.start_tls(context, server_hostname=TARGET, ssl_handshake_timeout=8)
        ww.write((
            f"GET /generate_204 HTTP/1.1\r\nHost: {TARGET}\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii"))
        await ww.drain()
        line = await asyncio.wait_for(rr.readline(), timeout=6)
        return line.startswith(b"HTTP/1.1 204 ") or line.startswith(b"HTTP/1.0 204 ")
    finally:
        ww.close()
        try:
            await ww.wait_closed()
        except (OSError, ConnectionError, ssl.SSLError):
            pass


class CarrierMonitor:
    """An edge circuit breaker: one failing carrier cannot evict the other.

    Startup defaults to SUSPECT until a real HTTPS-over-SOCKS probe passes.
    Recovery after quarantine requires cooldown AND two verified probes.
    """

    def __init__(self, upstreams, *, prober=None, clock=None,
                 interval=INTERVAL_SECONDS, stale_after=STALE_AFTER_SECONDS):
        self.upstreams = dict(upstreams)
        self.prober = prober or https_204_through_socks
        self.clock = clock or time.monotonic
        self.interval = interval
        self.stale_after = stale_after
        self.circuits = {
            name: Circuit(state=EdgeState.SUSPECT, suspect_after=1,
                          quarantine_after=2, cooldown_s=60,
                          restore_after=2)
            for name in self.upstreams
        }
        self.last_verified = {name: None for name in self.upstreams}
        self.probe_counts = {name: 0 for name in self.upstreams}

    def allowed(self, node):
        if node not in self.circuits:
            return False
        c = self.circuits[node]
        last = self.last_verified[node]
        return (c.admits_new_flows and last is not None
                and self.clock() - last <= self.stale_after)

    def report_connect_failure(self, node):
        if node in self.circuits:
            previous = self.circuits[node].state
            self.circuits[node].observe(False, self.clock(), active_probe=False)
            self._transition(node, previous)

    def _transition(self, name, previous):
        current = self.circuits[name].state
        if previous != current:
            print(f"LAB {name}: {previous.value} -> {current.value} "
                  "(only new TCP flows affected)", flush=True)

    async def check_one(self, node):
        previous = self.circuits[node].state
        ok = False
        try:
            ok = bool(await asyncio.wait_for(self.prober(self.upstreams[node]),
                                             timeout=14))
        except (OSError, ConnectionError, TimeoutError, ValueError,
                asyncio.TimeoutError, asyncio.IncompleteReadError, ssl.SSLError):
            pass
        self.probe_counts[node] += 1
        now = self.clock()
        if ok:
            self.last_verified[node] = now
        self.circuits[node].observe(ok, now, active_probe=True)
        self._transition(node, previous)
        return ok

    async def check_all(self):
        return await asyncio.gather(
            *(self.check_one(node) for node in self.upstreams)
        )

    async def run(self):
        while True:
            await self.check_all()
            await asyncio.sleep(self.interval)
