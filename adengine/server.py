"""Elbrus ads engine — remote MCP server.

ASGI app: bearer-token auth in front of a FastMCP streamable-HTTP app,
plus an unauthenticated /healthz endpoint for nginx/monitoring.

Run locally:
    ENGINE_BEARER_TOKEN=dev uvicorn adengine.server:app --port 8765
Production (systemd):
    uvicorn adengine.server:app --uds /run/elbrus/adengine.sock
"""

from __future__ import annotations

import hmac
import os

from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route

from adengine import ga4_tools, gads_tools, gsc_tools

def _transport_security():
    from mcp.server.transport_security import TransportSecuritySettings

    allowed_hosts = os.environ.get(
        "ENGINE_ALLOWED_HOSTS",
        # ":*" suffixes are wildcard-port patterns for local/dev use.
        "mcp.elbruscloud.com,localhost,localhost:*,127.0.0.1,127.0.0.1:*,testserver",
    ).split(",")
    return TransportSecuritySettings(
        allowed_hosts=[host.strip() for host in allowed_hosts if host.strip()],
    )


def create_mcp() -> FastMCP:
    server = FastMCP(
        "elbrus-ads-engine",
        instructions=(
            "Elbrus Cloud ad-management engine. Tools cover Google Ads (gads_*, "
            "read via GAQL plus writes: pause/enable, budgets, keywords, RSAs), "
            "Google Analytics 4 (ga4_*), and Search Console (gsc_*). Every Google "
            "Ads mutation defaults to dry_run=true (API validate_only); pass "
            "dry_run=false only after the change has been reviewed. New ads are "
            "always created PAUSED."
        ),
        stateless_http=True,
        json_response=True,
        transport_security=_transport_security(),
    )
    gads_tools.register(server)
    ga4_tools.register(server)
    gsc_tools.register(server)
    return server


mcp = create_mcp()


class BearerAuthMiddleware:
    """Rejects requests without the expected bearer token.

    /healthz is exempt. If ENGINE_BEARER_TOKEN is not configured the
    middleware fails closed (503) rather than serving unauthenticated.
    """

    EXEMPT_PATHS = {"/healthz"}

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] in self.EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        expected = os.environ.get("ENGINE_BEARER_TOKEN", "")
        if not expected:
            response = JSONResponse(
                {"error": "server_not_configured",
                 "detail": "ENGINE_BEARER_TOKEN is not set"},
                status_code=503,
            )
            await response(scope, receive, send)
            return

        provided = ""
        for name, value in scope.get("headers", []):
            if name == b"authorization":
                provided = value.decode("latin-1")
                break
        token = provided[7:] if provided.lower().startswith("bearer ") else ""

        if not token or not hmac.compare_digest(token, expected):
            response = JSONResponse(
                {"error": "unauthorized"},
                status_code=401,
                headers={"WWW-Authenticate": 'Bearer realm="elbrus-ads-engine"'},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


async def healthz(_request):
    return PlainTextResponse("ok")


def build_app(server: FastMCP | None = None):
    # A fresh FastMCP per app: the streamable-HTTP session manager only
    # supports a single lifespan run.
    inner = (server or create_mcp()).streamable_http_app()  # MCP at /mcp
    inner.router.routes.insert(0, Route("/healthz", healthz, methods=["GET"]))
    return BearerAuthMiddleware(inner)


app = build_app(mcp)
