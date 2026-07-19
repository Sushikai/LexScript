"""
DeepSeek API 客户端。
DeepSeek 兼容 OpenAI /chat/completions 协议,直接复用 MiniMaxLLM。
"""
from __future__ import annotations
from .minimax import MiniMaxLLM


class DeepSeekLLM(MiniMaxLLM):
    """DeepSeek adapter — 兼容 OpenAI Chat Completions 协议。"""

    name = "deepseek"
    default_model = "deepseek-chat"

    def __init__(self, api_key: str, base_url: str = "", model: str = ""):
        super().__init__(api_key, base_url or "https://api.deepseek.com", model)
