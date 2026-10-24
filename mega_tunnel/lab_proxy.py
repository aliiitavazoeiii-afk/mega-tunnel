"""Isolated TCP SOCKS5 router laboratory.

IMPORTANT: This is NOT a production tunnel, controller, or x-ui integration.
It binds only to 127.0.0.1, requires explicit --lab-only, connects ONLY to
local pre-existing SOCKS5 transport adapters, never opens an unauthenticated
public listener, never falls back to direct egress and does NOT handle UDP.
"""
import argparse
import asyncio
import json
import socket
from pathlib import Path
from .models import Edge, EdgeState, TrafficSnapshot, reference_inventory
from .routing import Router, NoHealthyRoute

MAX_BUFFER = 65536
TIMEOUT = 5.0


async def get_request(reader, writer):
    """Return a raw SOCKS5 CONNECT request with destination but no user metadata."""
    greeting = await asyncio.wait_for(reader.readexactly(2), TIMEOUT)
    if greeting[0] != 5 or greeting[1] > 16:
        raise ValueError("invalid SOCKS greeting")
    methods = await asyncio.wait_for(reader.readexactly(greeting[1]), TIMEOUT)
    if 0 not in methods:
        writer.write(b"\x05\xff")
        await writer.drain()
        raise ValueError("no supported auth")
    writer.write(b"\x05\x00")
    await writer.drain()
    req = await asyncio.wait_for(reader.readexactly(4), TIMEOUT)
    if req[:1] != b"\x05" or req[2] != 0:
        raise ValueError("invalid request")
    if req[1] != 1:  # UDP ASSOCIATE / BIND intentionally not implemented.
        writer.write(b"\x05\x07\x00\x01" + b"\0"*6)
        await writer.drain()
        raise ValueError("CONNECT only")
    atyp = req[3]
    if atyp == 1:
        dest = await reader.readexactly(4)
    elif atyp == 4:
        dest = await reader.readexactly(16)
    elif atyp == 3:
        n = await reader.readexactly(1)
        if n[0] == 0:
            raise ValueError("empty host")
        dest = n + await reader.readexactly(n[0])
    else:
        raise ValueError("invalid destination type")
    port = await reader.readexactly(2)
    if port == b"\0\0":
        raise ValueError("port zero")
    return req + dest + port


async def connect_upstream(port, request):
    """Dial only configured local SOCKS transport adapters; never DIRECT."""
    rr, ww = await asyncio.wait_for(
        asyncio.open_connection("127.0.0.1", port), TIMEOUT)
    try:
        ww.write(b"\x05\x01\x00")
        await ww.drain()
        if await asyncio.wait_for(rr.readexactly(2), TIMEOUT) != b"\x05\x00":
            raise ValueError("upstream SOCKS requires unexpected auth")
        ww.write(request)
        await ww.drain()
        hdr = await asyncio.wait_for(rr.readexactly(4), TIMEOUT)
        if hdr[0] != 5 or hdr[1] != 0 or hdr[2] != 0:
            raise ValueError("upstream refused CONNECT")
        if hdr[3] == 1:
            n = 4
        elif hdr[3] == 4:
            n = 16
        elif hdr[3] == 3:
            n = (await asyncio.wait_for(rr.readexactly(1), TIMEOUT))[0]
        else:
            raise ValueError("invalid upstream reply")
        await asyncio.wait_for(rr.readexactly(n + 2), TIMEOUT)
        return rr, ww
    except BaseException:
        ww.close()
        await ww.wait_closed()
        raise


async def pump(r, w):
    nbytes = 0
    while True:
        block = await r.read(MAX_BUFFER)
        if not block:
            break
        nbytes += len(block)
        w.write(block)
        await w.drain()
    if w.can_write_eof():
        try:
            w.write_eof()
            await w.drain()
        except (OSError, ConnectionError):
            pass
    return nbytes


class LabRouter:
    def __init__(self, gateway, upstreams, *, max_connections=256):
        if gateway not in ("Maya1", "Maya3"):
            raise ValueError("invalid gateway identity")
        inventory = reference_inventory()
        if not upstreams or not set(upstreams) <= set(inventory.foreigns):
            raise ValueError("missing or unknown transport adapters")
        for name, port in upstreams.items():
            if not isinstance(port, int) or not 1024 <= port <= 65535:
                raise ValueError("invalid loopback SOCKS port " + name)
        if not 1 <= max_connections <= 2000:
            raise ValueError("invalid lab concurrency limit")
        self.gateway = gateway
        self.upstreams = upstreams
        self.router = Router(inventory)
        self.byte_totals = {name: 0 for name in inventory.foreigns}
        self.active = {name: 0 for name in inventory.foreigns}
        self.sem = asyncio.Semaphore(max_connections)
        self.failures = {name: 0 for name in inventory.foreigns}

    def choose(self, excluded):
        edges = [
            Edge(self.gateway, f, EdgeState.HEALTHY, rtt_ms=50,
                 error_rate=min(self.failures[f] / 20.0, 1.0),
                 active_connections=self.active[f],
                 reachable=f not in excluded)
            for f in self.upstreams
        ]
        return self.router.choose(
            self.gateway, edges, TrafficSnapshot(self.byte_totals),
            allow_emergency=True
        ).foreign_id

    async def handle(self, reader, writer):
        async with self.sem:
            upstream = None
            node = None
            try:
                request = await get_request(reader, writer)
                excluded = set()
                while len(excluded) < len(self.upstreams):
                    try:
                        node = self.choose(excluded)
                    except NoHealthyRoute:
                        break
                    try:
                        upstream = await connect_upstream(self.upstreams[node], request)
                        self.failures[node] = max(0, self.failures[node]-1)
                        break
                    except (OSError, ValueError, TimeoutError, asyncio.TimeoutError,
                            asyncio.IncompleteReadError):
                        self.failures[node] += 1
                        excluded.add(node)
                if upstream is None:
                    writer.write(b"\x05\x04\x00\x01" + b"\0"*6)
                    await writer.drain()
                    return
                self.active[node] += 1
                writer.write(b"\x05\x00\x00\x01" + b"\0"*6)
                await writer.drain()
                rr, ww = upstream
                up, down = await asyncio.gather(pump(reader, ww), pump(rr, writer))
                self.byte_totals[node] += up + down
            except (ValueError, OSError, ConnectionError, EOFError,
                    asyncio.TimeoutError, asyncio.IncompleteReadError):
                pass
            finally:
                if node is not None and upstream is not None:
                    self.active[node] = max(0, self.active[node]-1)
                if upstream is not None:
                    upstream[1].close()
                    try:
                        await upstream[1].wait_closed()
                    except OSError:
                        pass
                writer.close()
                try:
                    await writer.wait_closed()
                except OSError:
                    pass


def parse_config(path):
    c = json.loads(Path(path).read_text())
    if c.get("lab_only") is not True:
        raise ValueError("configuration must explicitly declare lab_only true")
    if c.get("listen_host") != "127.0.0.1":
        raise ValueError("public proxy listeners are forbidden")
    port = c.get("listen_port")
    if not isinstance(port, int) or port != 17990:
        raise ValueError("lab port must be 17990")
    upstreams = c.get("upstreams")
    if not isinstance(upstreams, dict):
        raise ValueError("upstreams must be a mapping")
    return c["gateway"], port, upstreams


async def serve(config):
    gateway, port, upstreams = parse_config(config)
    router = LabRouter(gateway, upstreams)
    server = await asyncio.start_server(router.handle, "127.0.0.1", port,
                                        limit=MAX_BUFFER)
    print("LAB-ONLY listening on 127.0.0.1:17990 (no x-ui changes)", flush=True)
    async with server:
        await server.serve_forever()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", required=True)
    p.add_argument("--lab-only", action="store_true")
    args = p.parse_args()
    if not args.lab_only:
        p.error("not a production router; explicit --lab-only is required")
    asyncio.run(serve(args.config))


if __name__ == "__main__":
    main()
