"""健康检查与基础架构测试。"""
from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    """GET /api/v1/health 返回 ok=true。"""
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["service"] == "LexScript"
    assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_info_endpoint(client: AsyncClient):
    """GET /api/v1/info 返回服务信息。"""
    resp = await client.get("/api/v1/info")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["service"] == "LexScript"
    assert isinstance(data.get("lan_ip"), (str, type(None)))
    assert data["local_url"].startswith("http://")


@pytest.mark.asyncio
async def test_root_serves_html(client: AsyncClient):
    """GET / 返回 HTML 页面。"""
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_spa_fallback(client: AsyncClient):
    """未知路径返回 SPA fallback (非 /api/)。"""
    resp = await client.get("/some-unknown-path")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_api_404(client: AsyncClient):
    """未注册的 /api/ 路径返回 404 JSON。"""
    resp = await client.get("/api/v1/nonexistent")
    assert resp.status_code == 404
