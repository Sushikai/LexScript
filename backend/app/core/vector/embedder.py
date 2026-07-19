"""Embedding 客户端 — 根据 provider 自动选择 embedding 端点。"""
from __future__ import annotations
import os
import httpx
from loguru import logger

# 各 provider 的 embedding 配置
EMBEDDING_CONFIG: dict[str, dict] = {
    "minimax": {
        "base_url": "https://api.minimax.chat/v1",
        "model": "embo-01",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-embedding",
    },
    "moonshot": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-embedding",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "text-embedding-v3",
    },
}


def _resolve_embedding_config(provider: str = "", api_key: str = "",
                                base_url: str = "", model: str = "") -> tuple[str, str, str]:
    """根据 provider 解析 embedding 的 api_key / base_url / model。"""
    if not provider:
        provider = "minimax"
    cfg = EMBEDDING_CONFIG.get(provider, EMBEDDING_CONFIG["minimax"])
    return (
        api_key,
        base_url or cfg["base_url"],
        model or cfg["model"],
    )


class Embedder:
    """Provider-aware embedding 客户端。"""

    def __init__(self, api_key: str = "", base_url: str = "", model: str = "",
                 provider: str = ""):
        # 使用 embedding 专用 provider（与 chat LLM provider 独立）
        if not provider:
            from app.config import EMBEDDING_PROVIDER
            provider = EMBEDDING_PROVIDER
        # 若未传入 api_key，按 provider 自动查找
        if not api_key:
            if provider == "minimax":
                api_key = os.environ.get("MINIMAX_API_KEY", "")
            elif provider == "deepseek":
                api_key = os.environ.get("DEEPSEEK_API_KEY", "")
            if not api_key:
                from app.services.config_service import get_config
                api_key = get_config(f"{provider}_api_key") or get_config("llm_api_key") or ""
        self.api_key = api_key
        self.provider = provider
        _, self.base_url, self.model = _resolve_embedding_config(provider, api_key, base_url, model)
        self._client = httpx.Client(timeout=30)

    def _build_payload(self, texts: list[str], mode: str = "db") -> dict:
        """根据 provider 构建 embed 请求体。
        mode: "db" 索引入库, "query" 搜索查询（MiniMax 区分二者）。
        """
        if self.provider == "minimax":
            return {"model": self.model, "texts": texts, "type": mode}
        return {"model": self.model, "input": texts}

    def _parse_response(self, data: dict) -> list[list[float]]:
        """根据 provider 解析 embedding 响应。"""
        if self.provider == "minimax":
            return data.get("vectors", [])
        return [d["embedding"] for d in sorted(data["data"], key=lambda x: x["index"])]

    def embed(self, texts: list[str], mode: str = "db") -> list[list[float]]:
        """批量文本 → 向量。mode: "db" 入库, "query" 搜索（MiniMax 区分二者）。"""
        if not texts:
            return []
        try:
            r = self._client.post(
                f"{self.base_url}/embeddings",
                json=self._build_payload(texts, mode=mode),
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            if r.status_code != 200:
                logger.warning(f"[embedder] HTTP {r.status_code}: {r.text[:200]}")
                return self._fallback(texts)
            data = r.json()
            return self._parse_response(data)
        except Exception as e:
            logger.warning(f"[embedder] error: {e}")
            return self._fallback(texts)

    def _fallback(self, texts: list[str]) -> list[list[float]]:
        """降级:零向量(API embedding 不可用时的保底)。"""
        logger.warning("[embedder] Embedding API 不可用，返回零向量。"
                       "请配置 MiniMax API Key 或 provider 的 embedding 模型。")
        dim = 1536
        return [[0.0] * dim for _ in texts]

    def close(self):
        if self._client:
            self._client.close()