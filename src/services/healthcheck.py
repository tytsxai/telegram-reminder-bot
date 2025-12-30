"""Simple HTTP health check server."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from typing import Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

HealthCheck = Callable[[], bool | dict | Awaitable[bool] | Awaitable[dict]]


class HealthCheckServer:
    """Lightweight HTTP health check server."""

    def __init__(
        self,
        host: str,
        port: int,
        path: str = "/healthz",
        check: Optional[HealthCheck] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.path = path
        self.check = check
        self._server: Optional[asyncio.AbstractServer] = None

    async def start(self) -> None:
        """Start the server."""
        self._server = await asyncio.start_server(self._handle, self.host, self.port)
        sockets = self._server.sockets or []
        if sockets:
            self.port = sockets[0].getsockname()[1]
        logger.info("Healthcheck server started on %s:%s", self.host, self.port)

    async def stop(self) -> None:
        """Stop the server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("Healthcheck server stopped")
            self._server = None

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            request_line = await reader.readline()
            if not request_line:
                return
            parts = request_line.decode(errors="ignore").strip().split()
            method = parts[0] if len(parts) >= 1 else ""
            path = parts[1] if len(parts) >= 2 else ""

            # Drain headers
            while True:
                line = await reader.readline()
                if not line or line in (b"\r\n", b"\n"):
                    break

            if method not in {"GET", "HEAD"}:
                await self._respond(
                    writer, 405, {"ok": False, "status": "method_not_allowed"}
                )
                return

            if path != self.path:
                await self._respond(writer, 404, {"ok": False, "status": "not_found"})
                return

            ok, payload = await self._evaluate_check()
            status_code = 200 if ok else 503
            await self._respond(
                writer, status_code, payload, include_body=(method == "GET")
            )
        except Exception as exc:
            logger.exception("Healthcheck error: %s", exc)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _evaluate_check(self) -> tuple[bool, dict]:
        if self.check is None:
            return True, {"ok": True, "status": "ok"}
        result = self.check()
        if inspect.isawaitable(result):
            result = await result
        if isinstance(result, dict):
            ok = bool(result.get("ok", True))
            payload = result
        elif isinstance(result, bool):
            ok = result
            payload = {"ok": ok, "status": "ok" if ok else "unhealthy"}
        else:
            ok = True
            payload = {"ok": True, "status": "ok"}
        return ok, payload

    async def _respond(
        self,
        writer: asyncio.StreamWriter,
        status_code: int,
        payload: dict,
        include_body: bool = True,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        reason = {
            200: "OK",
            404: "Not Found",
            405: "Method Not Allowed",
            503: "Service Unavailable",
        }.get(status_code, "OK")
        headers = [
            f"HTTP/1.1 {status_code} {reason}",
            "Content-Type: application/json; charset=utf-8",
            f"Content-Length: {len(body) if include_body else 0}",
            "Connection: close",
            "",
            "",
        ]
        writer.write("\r\n".join(headers).encode("utf-8"))
        if include_body and body:
            writer.write(body)
        await writer.drain()
