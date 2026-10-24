import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from mega_tunnel.lab_proxy import LabRouter, parse_config
from mega_tunnel.models import EdgeState
from mega_tunnel.routing import NoHealthyRoute


async def mock_socks(reader, writer):
    """In-process fake foreign SOCKS5, no Internet connection."""
    try:
        msg = await reader.readexactly(3)
        assert msg == b"\x05\x01\x00"
        writer.write(b"\x05\x00")
        await writer.drain()
        req = await reader.readexactly(4)
        assert req == b"\x05\x01\x00\x01"
        _ = await reader.readexactly(6)
        writer.write(b"\x05\x00\x00\x01" + b"\0"*6)
        await writer.drain()
        data = await reader.readexactly(4)
        if data == b"ping":
            writer.write(b"pong")
            await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


async def run_one_request(port):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        writer.write(b"\x05\x01\x00")
        await writer.drain()
        greeting = await asyncio.wait_for(reader.readexactly(2), timeout=4)
        if greeting != b"\x05\x00":
            return greeting, b""
        writer.write(b"\x05\x01\x00\x01\x01\x02\x03\x04\x00\x50")
        await writer.drain()
        status = await asyncio.wait_for(reader.readexactly(10), timeout=4)
        if status[1] != 0:
            return status, b""
        writer.write(b"ping")
        await writer.drain()
        response = await asyncio.wait_for(reader.readexactly(4), timeout=4)
        return status, response
    finally:
        writer.close()
        await writer.wait_closed()


class LabProxyTests(unittest.IsolatedAsyncioTestCase):
    async def test_through_fake_upstream(self):
        upstream = await asyncio.start_server(mock_socks, "127.0.0.1", 0)
        upstream_port = upstream.sockets[0].getsockname()[1]
        router = LabRouter("Maya1", {"F1": upstream_port})
        server = await asyncio.start_server(router.handle, "127.0.0.1", 0)
        local_port = server.sockets[0].getsockname()[1]
        try:
            result, payload = await run_one_request(local_port)
            self.assertEqual(result[:2], b"\x05\x00")
            self.assertEqual(payload, b"pong")
        finally:
            server.close()
            upstream.close()
            await server.wait_closed()
            await upstream.wait_closed()

    async def test_40_parallel_flows_no_shared_single_tcp_socket(self):
        upstream = await asyncio.start_server(mock_socks, "127.0.0.1", 0)
        upstream_port = upstream.sockets[0].getsockname()[1]
        router = LabRouter("Maya1", {"F1": upstream_port}, max_connections=80)
        server = await asyncio.start_server(router.handle, "127.0.0.1", 0)
        local_port = server.sockets[0].getsockname()[1]
        try:
            outcomes = await asyncio.wait_for(
                asyncio.gather(*(run_one_request(local_port) for _ in range(40))),
                timeout=15
            )
            self.assertEqual(len(outcomes), 40)
            for response, payload in outcomes:
                self.assertEqual(response[:2], b"\x05\x00")
                self.assertEqual(payload, b"pong")
        finally:
            server.close()
            upstream.close()
            await server.wait_closed()
            await upstream.wait_closed()

    async def test_retry_alternate_transport_on_new_connect(self):
        upstream = await asyncio.start_server(mock_socks, "127.0.0.1", 0)
        upstream_port = upstream.sockets[0].getsockname()[1]
        router = LabRouter("Maya1", {"F1": 65498, "F2": upstream_port})
        router.active["F2"] = 1500  # prefer trying broken F1 first
        server = await asyncio.start_server(router.handle, "127.0.0.1", 0)
        local_port = server.sockets[0].getsockname()[1]
        try:
            response, payload = await run_one_request(local_port)
            self.assertEqual(response[:2], b"\x05\x00")
            self.assertEqual(payload, b"pong")
            self.assertGreaterEqual(router.failures["F1"], 1)
        finally:
            server.close()
            upstream.close()
            await server.wait_closed()
            await upstream.wait_closed()

    async def test_no_direct_fallback_when_upstream_down(self):
        router = LabRouter("Maya1", {"F1": 65499})
        server = await asyncio.start_server(router.handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        try:
            status, _ = await run_one_request(port)
            self.assertEqual(status[1], 4)
        finally:
            server.close()
            await server.wait_closed()

    async def test_connect_only_rejects_udp_associate(self):
        router = LabRouter("Maya1", {"F1": 65499})
        server = await asyncio.start_server(router.handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            try:
                writer.write(b"\x05\x01\x00")
                await writer.drain()
                self.assertEqual(await reader.readexactly(2), b"\x05\x00")
                writer.write(b"\x05\x03\x00\x01" + b"\0"*6)
                await writer.drain()
                response = await reader.readexactly(10)
                self.assertEqual(response[1], 7)
            finally:
                writer.close()
                await writer.wait_closed()
        finally:
            server.close()
            await server.wait_closed()

    def test_no_public_bind_or_production_mode(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/"test.json"
            p.write_text(json.dumps({
                "lab_only": True,
                "listen_host": "0.0.0.0",
                "listen_port": 17990,
                "gateway": "Maya1",
                "upstreams": {"F1": 17991}
            }))
            with self.assertRaises(ValueError):
                parse_config(p)
            p.write_text(json.dumps({
                "lab_only": False,
                "listen_host": "127.0.0.1",
                "listen_port": 17990,
                "gateway": "Maya1",
                "upstreams": {"F1": 17991}
            }))
            with self.assertRaises(ValueError):
                parse_config(p)

    def test_unknown_foreign_rejected(self):
        with self.assertRaises(ValueError):
            LabRouter("Maya1", {"OTHER": 17991})
