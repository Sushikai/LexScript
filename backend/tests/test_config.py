"""系统配置 API 测试。"""
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
async def test_config_endpoint(client: AsyncClient):
    """GET /api/v1/config 返回配置。"""
    resp = await client.get("/api/v1/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert isinstance(data.get("data"), dict)


@pytest.mark.asyncio
async def test_models_endpoint(client: AsyncClient):
    """GET /api/v1/config/models 返回模型列表。"""
    resp = await client.get("/api/v1/config/models")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert isinstance(data.get("data"), list)
    assert len(data["data"]) >= 4  # 至少 4 个模型


@pytest.mark.asyncio
async def test_providers_endpoint(client: AsyncClient):
    """GET /api/v1/config/providers 返回提供商列表。"""
    resp = await client.get("/api/v1/config/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "data" in data


@pytest.mark.asyncio
async def test_test_connection_invalid_key(client: AsyncClient):
    """POST /api/v1/config/test 无效 key 应失败。"""
    resp = await client.post(
        "/api/v1/config/test",
        json={"api_key": "short", "base_url": "https://api.MiniMax.io/v1", "model": "MiniMax-M3"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # 无效 key → 应当失败
    assert data["ok"] is False or data.get("code") == "INVALID_KEY"
