"""
Claude API 客户端 — 实现 Anthropic Messages API。
POST /v1/messages, x-api-key header, anthropic-version: 2023-06-01。
"""
from __future__ import annotations
import json
import asyncio
from typing import AsyncIterator
import httpx
from loguru import logger
from .base import BaseLLM, LLMMessage, LLMResponse


class ClaudeLLM(BaseLLM):
    """Claude Messages API 适配器。"""

    name = "claude"
    default_model = "claude-3-5-sonnet-20241022"

    def __init__(self, api_key: str, base_url: str = "", model: str = ""):
        super().__init__(api_key, base_url or "https://api.anthropic.com/v1", model)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(120, connect=15),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _build_headers(self, stream: bool = False) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def _convert_messages(self, messages: list[LLMMessage]) -> tuple[list[dict], str | None]:
        """Claude API 把 system 拆到顶层。"""
        system = None
        converted = []
        for m in messages:
            if m.role == "system":
                system = m.content
            else:
                converted.append({"role": m.role, "content": m.content})
        return converted, system

    async def chat(self, messages: list[LLMMessage], **kwargs) -> LLMResponse:
        """非流式对话。"""
        msgs, system = self._convert_messages(messages)
        payload: dict = {
            "model": self.model,
            "messages": msgs,
            "max_tokens": kwargs.get("max_tokens", 2048),
        }
        if system:
            payload["system"] = system
        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]

        client = await self._get_client()
        for attempt in range(3):
            try:
                r = await client.post(
                    "/messages",
                    json=payload,
                    headers=self._build_headers(),
                )
                if r.status_code != 200:
                    raise RuntimeError(f"Claude HTTP {r.status_code}: {r.text[:300]}")
                data = r.json()
                content = ""
                for block in data.get("content", []):
                    if block.get("type") == "text":
                        content += block.get("text", "")
                return LLMResponse(
                    content=content,
                    model=data.get("model", self.model),
                    tokens_in=data.get("usage", {}).get("input_tokens", 0),
                    tokens_out=data.get("usage", {}).get("output_tokens", 0),
                    finish_reason=data.get("stop_reason", "stop"),
                    raw=data,
                )
            except Exception as e:
                logger.warning(f"[claude] chat attempt={attempt} err={e}")
                if attempt < 2:
                    await asyncio.sleep(0.5 * (2 ** attempt))
                    continue
                raise

    async def stream(self, messages: list[LLMMessage], **kwargs) -> AsyncIterator[str]:
        """SSE 流式对话,解析 content_block_delta 事件。"""
        msgs, system = self._convert_messages(messages)
        payload: dict = {
            "model": self.model,
            "messages": msgs,
            "max_tokens": kwargs.get("max_tokens", 2048),
            "stream": True,
        }
        if system:
            payload["system"] = system
        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]

        client = await self._get_client()
        async with client.stream(
            "POST",
            "/messages",
            json=payload,
            headers=self._build_headers(),
        ) as r:
            if r.status_code != 200:
                body = await r.aread()
                raise RuntimeError(f"Claude HTTP {r.status_code}: {body[:300].decode()}")
            async for line in r.aiter_lines():
                line = line.strip()
                if not line:
                    continue
                if line.startswith("event: "):
                    continue  # event type line, next line has data
                if line.startswith("data: "):
                    chunk_data = line[6:].strip()
                    if chunk_data == "[DONE]":
                        break
                    try:
                        event = json.loads(chunk_data)
                        e_type = event.get("type", "")
                        if e_type == "content_block_delta":
                            delta = event.get("delta", {})
                            text = delta.get("text", "")
                            if text:
                                yield text
                    except json.JSONDecodeError:
                        continue
