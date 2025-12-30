"""Healthcheck server tests."""

import asyncio
import json

import pytest

from src.services.healthcheck import HealthCheckServer


async def _fetch_raw(server: HealthCheckServer, payload: bytes) -> bytes:
    reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
    writer.write(payload)
    await writer.drain()
    data = await reader.read()
    writer.close()
    await writer.wait_closed()
    return data


@pytest.mark.asyncio
async def test_healthcheck_ok():
    server = HealthCheckServer("127.0.0.1", 0)
    await server.start()
    try:
        data = await _fetch_raw(
            server, b"GET /healthz HTTP/1.1\r\nHost: localhost\r\n\r\n"
        )
    finally:
        await server.stop()

    assert b"200 OK" in data
    body = data.split(b"\r\n\r\n", 1)[1]
    payload = json.loads(body.decode("utf-8"))
    assert payload["ok"] is True


@pytest.mark.asyncio
async def test_healthcheck_unhealthy():
    async def check():
        return {"ok": False, "status": "db_error"}

    server = HealthCheckServer("127.0.0.1", 0, check=check)
    await server.start()
    try:
        data = await _fetch_raw(
            server, b"GET /healthz HTTP/1.1\r\nHost: localhost\r\n\r\n"
        )
    finally:
        await server.stop()

    assert b"503 Service Unavailable" in data


@pytest.mark.asyncio
async def test_healthcheck_not_found():
    server = HealthCheckServer("127.0.0.1", 0)
    await server.start()
    try:
        data = await _fetch_raw(
            server, b"GET /missing HTTP/1.1\r\nHost: localhost\r\n\r\n"
        )
    finally:
        await server.stop()

    assert b"404 Not Found" in data


@pytest.mark.asyncio
async def test_healthcheck_method_not_allowed():
    server = HealthCheckServer("127.0.0.1", 0)
    await server.start()
    try:
        data = await _fetch_raw(
            server, b"POST /healthz HTTP/1.1\r\nHost: localhost\r\n\r\n"
        )
    finally:
        await server.stop()

    assert b"405 Method Not Allowed" in data


@pytest.mark.asyncio
async def test_healthcheck_boolean_payload():
    server = HealthCheckServer("127.0.0.1", 0, check=lambda: False)
    await server.start()
    try:
        data = await _fetch_raw(
            server, b"GET /healthz HTTP/1.1\r\nHost: localhost\r\n\r\n"
        )
    finally:
        await server.stop()

    assert b"503 Service Unavailable" in data
