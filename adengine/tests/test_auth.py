"""Bearer-auth middleware behaviour."""

import pytest
from starlette.testclient import TestClient

from adengine.server import build_app

INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}
MCP_HEADERS = {"Accept": "application/json, text/event-stream"}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("ENGINE_BEARER_TOKEN", "secret-token")
    # Context manager runs the Starlette lifespan, which starts the MCP
    # streamable-HTTP session manager.
    with TestClient(build_app()) as test_client:
        yield test_client


def test_healthz_needs_no_auth(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.text == "ok"


def test_mcp_without_token_is_401(client):
    response = client.post("/mcp", json=INITIALIZE, headers=MCP_HEADERS)
    assert response.status_code == 401


def test_mcp_with_wrong_token_is_401(client):
    response = client.post(
        "/mcp", json=INITIALIZE,
        headers={**MCP_HEADERS, "Authorization": "Bearer wrong"},
    )
    assert response.status_code == 401


def test_mcp_unconfigured_token_fails_closed(monkeypatch):
    monkeypatch.delenv("ENGINE_BEARER_TOKEN", raising=False)
    with TestClient(build_app()) as unconfigured:
        response = unconfigured.post("/mcp", json=INITIALIZE, headers=MCP_HEADERS)
    assert response.status_code == 503


def test_mcp_with_correct_token_initializes(client):
    response = client.post(
        "/mcp", json=INITIALIZE,
        headers={**MCP_HEADERS, "Authorization": "Bearer secret-token"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["serverInfo"]["name"] == "elbrus-ads-engine"
