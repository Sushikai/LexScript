"""
/api/v1/config 端点 — 配置读写 + LLM 连通性测试 + Provider 发现。
GET:        返回脱敏后的公开配置
PATCH:      批量更新(多 Provider Key / Base URL / Model)
GET /providers: 返回支持的 Provider 列表
GET /models:    返回可选模型列表
POST /test:     用临时传入的 key/model 测试连通性(不保存)
POST /test_saved: 用已保存的配置测试
"""
from __future__ import annotations
import time
import asyncio
from fastapi import APIRouter, Body
from pydantic import BaseModel
from app.services.config_service import get_all_public, update_batch, get_config, set_config
from app.core.llm.registry import (
    get_llm,
    get_llm_from_config,
    list_models,
    list_providers,
    get_provider_info,
    PROVIDER_CONFIGS,
)
from app.api.v1 import router as v1_router

# 复用 v1_router(自带 /api/v1 prefix),只需再加 /config
router = APIRouter(prefix="/config", tags=["config"])
v1_router.include_router(router)


class ConfigUpdate(BaseModel):
    # 新通用 Key
    llm_provider: str | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    # 短别名(前端发送用 provider/api_key/base_url/model)
    provider: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    # 旧 Key(向后兼容)
    minimax_api_key: str | None = None
    minimax_base_url: str | None = None
    minimax_model: str | None = None
    # Alpha GPT(双模型)
    alpha_gpt_api_key: str | None = None
    alpha_gpt_model: str | None = None
    # 其他
    embedding_provider: str | None = None
    embedding_model: str | None = None
    statute_api_key: str | None = None
    statute_api_base: str | None = None
    active_role: str | None = None


class TestRequest(BaseModel):
    api_key: str
    base_url: str = "https://api.MiniMax.io/v1"
    model: str = "MiniMax-M3"


@router.get("")
def list_config():
    """返回所有公开配置(密钥脱敏)。"""
    return {"ok": True, "data": get_all_public()}


@router.patch("")
def update_config(payload: ConfigUpdate):
    """批量更新配置。"""
    data = payload.model_dump(exclude_none=True)

    # 短别名 → 标准 key
    _short_to_long = {
        "provider": "llm_provider",
        "api_key": "llm_api_key",
        "base_url": "llm_base_url",
        "model": "llm_model",
    }
    for short_k, long_k in _short_to_long.items():
        if short_k in data and long_k not in data:
            data[long_k] = data.pop(short_k)
        elif short_k in data:
            data.pop(short_k)

    # 向后兼容:如果用户只传了旧 minimax_xxx,同步写一份到新 key
    _old_to_new = {
        "minimax_api_key": "llm_api_key",
        "minimax_base_url": "llm_base_url",
        "minimax_model": "llm_model",
    }
    for old_k, new_k in _old_to_new.items():
        if old_k in data and new_k not in data:
            data[new_k] = data[old_k]
    # 如果没设 provider,但设了 api_key,默认用 minimax
    if "llm_api_key" in data and "llm_provider" not in data:
        existing_provider = get_config("llm_provider")
        if not existing_provider:
            data["llm_provider"] = "minimax"

    update_batch(data)
    return {"ok": True, "data": get_all_public()}


@router.get("/agent/prompt")
def agent_prompt(refresh: bool = False):
    """返回 Agent 系统提示词(主控 + 分场景)。"""
    from app.core.agent.prompts import MASTER_SYSTEM_PROMPT, SCENE_PROMPTS
    return {
        "ok": True,
        "data": {
            "system_prompt": MASTER_SYSTEM_PROMPT,
            "scene_prompts": SCENE_PROMPTS,
            "scene_names": list(SCENE_PROMPTS.keys()),
        },
    }


@router.get("/providers")
def available_providers():
    """返回支持的 Provider 列表(含 base_url 与可用模型)。"""
    return {"ok": True, "data": PROVIDER_CONFIGS}


@router.get("/models")
def available_models():
    """返回可选模型列表。"""
    return {"ok": True, "data": list_models()}


@router.post("/test")
async def test_connection(req: TestRequest):
    """用临时传入的 key/model 测试连通性(不保存)。"""
    if not req.api_key or len(req.api_key) < 8:
        return {"ok": False, "code": "INVALID_KEY", "message": "API Key 长度不足", "data": None}
    llm = get_llm(api_key=req.api_key, base_url=req.base_url, model=req.model)
    t0 = time.time()
    try:
        resp = await asyncio_wait_with_timeout(llm.test("你好"), timeout=20)
        dt = (time.time() - t0) * 1000
        return {
            "ok": True,
            "data": {
                "latency_ms": round(dt, 1),
                "model": resp.model,
                "reply": resp.content,
                "tokens_in": resp.tokens_in,
                "tokens_out": resp.tokens_out,
            },
        }
    except Exception as e:
        dt = (time.time() - t0) * 1000
        return {
            "ok": False,
            "code": "TEST_FAILED",
            "message": str(e),
            "data": {"latency_ms": round(dt, 1)},
        }


@router.post("/test_saved")
async def test_saved_config():
    """用已保存的配置测试连通性。"""
    llm = get_llm_from_config()
    if not llm:
        return {"ok": False, "code": "NOT_CONFIGURED", "message": "尚未配置 API Key"}
    t0 = time.time()
    try:
        resp = await asyncio_wait_with_timeout(llm.test("你好,请回复 OK"), timeout=20)
        dt = (time.time() - t0) * 1000
        return {
            "ok": True,
            "data": {
                "latency_ms": round(dt, 1),
                "model": resp.model,
                "reply": resp.content,
                "tokens_in": resp.tokens_in,
                "tokens_out": resp.tokens_out,
            },
        }
    except Exception as e:
        dt = (time.time() - t0) * 1000
        return {
            "ok": False,
            "code": "TEST_FAILED",
            "message": str(e),
            "data": {"latency_ms": round(dt, 1)},
        }


async def asyncio_wait_with_timeout(coro, timeout: float):
    """带超时跑的协程。"""
    return await asyncio.wait_for(coro, timeout=timeout)
