"""LLM 注册表 — 多 Provider 支持,根据用户配置返回对应的 adapter 实例。"""
from __future__ import annotations
from .base import BaseLLM
from .minimax import MiniMaxLLM
from .deepseek import DeepSeekLLM
from .claude import ClaudeLLM
from ..security import decrypt
from app.db.database import query

# Provider 元信息 — 完整国产模型列表
# 所有 OpenAI /chat/completions 兼容的 provider 复用 MiniMaxLLM adapter
PROVIDER_CONFIGS = {
    "minimax":      {"name": "MiniMax（海螺AI）",    "base_url": "https://api.minimax.chat/v1",               "models": ["MiniMax-M3", "MiniMax-M2"],                                "default_model": "MiniMax-M3"},
    "deepseek":     {"name": "DeepSeek（深度求索）",    "base_url": "https://api.deepseek.com/v1",             "models": ["deepseek-chat", "deepseek-reasoner"],                        "default_model": "deepseek-chat"},
    "moonshot":     {"name": "月之暗面（Kimi）",       "base_url": "https://api.moonshot.cn/v1",              "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],    "default_model": "moonshot-v1-8k"},
    "qwen":         {"name": "阿里通义千问",           "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "models": ["qwen-max", "qwen-plus", "qwen-turbo", "qwen2.5-72b-instruct"], "default_model": "qwen-plus"},
    "zhipu":        {"name": "智谱AI（GLM）",         "base_url": "https://open.bigmodel.cn/api/paas/v4",    "models": ["glm-4-plus", "glm-4-0520", "glm-4-air", "glm-4-flash"],    "default_model": "glm-4-flash"},
    "baichuan":     {"name": "百川智能",               "base_url": "https://api.baichuan-ai.com/v1",          "models": ["Baichuan4-Turbo", "Baichuan3-Turbo"],                       "default_model": "Baichuan4-Turbo"},
    "yi":           {"name": "零一万物（Yi）",         "base_url": "https://api.lingyiwanwu.com/v1",          "models": ["yi-lightning", "yi-medium", "yi-large", "yi-large-turbo"],  "default_model": "yi-lightning"},
    "spark":        {"name": "讯飞星火",               "base_url": "https://spark-api-open.xf-yun.com/v1",    "models": ["4.0Ultra", "generalv3.5", "generalv3"],                     "default_model": "generalv3.5"},
    "doubao":       {"name": "字节豆包",               "base_url": "https://ark.cn-beijing.volces.com/api/v3","models": ["doubao-pro-32k", "doubao-pro-128k", "doubao-lite-128k"],    "default_model": "doubao-pro-32k"},
    "hunyuan":      {"name": "腾讯混元",               "base_url": "https://api.hunyuan.cloud.tencent.com/v1","models": ["hunyuan-pro", "hunyuan-standard", "hunyuan-lite"],           "default_model": "hunyuan-lite"},
    "siliconflow":  {"name": "硅基流动",               "base_url": "https://api.siliconflow.cn/v1",           "models": ["Qwen/Qwen2.5-72B-Instruct", "deepseek-ai/DeepSeek-V3", "THUDM/glm-4-9b-chat", "meta-llama/Llama-3.3-70B-Instruct"], "default_model": "Qwen/Qwen2.5-72B-Instruct"},
    "openai":       {"name": "OpenAI",                 "base_url": "https://api.openai.com/v1",               "models": ["gpt-4o", "gpt-4o-mini", "gpt-4.1"],                        "default_model": "gpt-4o"},
    "claude":       {"name": "Claude（Anthropic）",    "base_url": "https://api.anthropic.com/v1",             "models": ["claude-sonnet-4-20250514", "claude-haiku-3-5-20241022"],    "default_model": "claude-sonnet-4-20250514"},
}

# Provider -> Adapter class
_PROVIDER_ADAPTERS = {
    "minimax": MiniMaxLLM,
    "deepseek": DeepSeekLLM,
    "moonshot": MiniMaxLLM,
    "qwen": MiniMaxLLM,
    "zhipu": MiniMaxLLM,
    "baichuan": MiniMaxLLM,
    "yi": MiniMaxLLM,
    "spark": MiniMaxLLM,
    "doubao": MiniMaxLLM,
    "hunyuan": MiniMaxLLM,
    "siliconflow": MiniMaxLLM,
    "claude": ClaudeLLM,
    "openai": MiniMaxLLM,
}

# 旧配置 key → 新配置 key 映射(向后兼容)
_OLD_KEY_MAP = {
    "minimax_api_key": "llm_api_key",
    "minimax_base_url": "llm_base_url",
    "minimax_model": "llm_model",
}

# 配置 key 常量
CFG_PROVIDER = "llm_provider"
CFG_API_KEY = "llm_api_key"
CFG_BASE_URL = "llm_base_url"
CFG_MODEL = "llm_model"


def list_providers() -> list[str]:
    """返回所有支持的 provider 名称列表。"""
    return list(PROVIDER_CONFIGS.keys())


def get_provider_info(provider: str) -> dict | None:
    """返回 provider 配置信息(base_url, models 列表)。"""
    return PROVIDER_CONFIGS.get(provider)


def list_models() -> list[str]:
    """所有 provider 的模型列表(平铺)。"""
    models = []
    for info in PROVIDER_CONFIGS.values():
        models.extend(info["models"])
    return models


def _read_config(key: str) -> str | None:
    """从 system_config 表读配置(自动解密)。"""
    from app.services.config_service import get_config
    return get_config(key)


def _get_cfg_or_fallback(new_key: str, old_key: str) -> str | None:
    """优先读新 key,fallback 到旧 key。"""
    v = _read_config(new_key)
    if v:
        return v
    return _read_config(old_key)


def get_llm_from_config() -> BaseLLM | None:
    """从系统配置读 provider / API key / model / base_url,返回 LLM 实例。未配置返回 None。"""
    rows = query("SELECT key, value_encrypted FROM system_config")
    cfg = {r["key"]: r["value_encrypted"] for r in rows}

    # 读 provider (默认 minimax)
    provider = (
        decrypt(cfg.get(CFG_PROVIDER, ""))
        or _read_config(CFG_PROVIDER)
        or "minimax"
    )

    # 读 API key (新 key 优先,fallback 旧 key)
    api_key = _get_cfg_or_fallback("llm_api_key", "minimax_api_key")
    if not api_key:
        # 也试从 cfg dict 读解密
        encrypted = cfg.get("llm_api_key") or cfg.get("minimax_api_key", "")
        api_key = decrypt(encrypted) if encrypted else ""
    if not api_key:
        return None

    base_url = _get_cfg_or_fallback("llm_base_url", "minimax_base_url")
    model = _get_cfg_or_fallback("llm_model", "minimax_model")

    adapter_cls = _PROVIDER_ADAPTERS.get(provider, MiniMaxLLM)
    return adapter_cls(
        api_key=api_key,
        base_url=base_url or PROVIDER_CONFIGS.get(provider, {}).get("base_url", ""),
        model=model or "",
    )


def _detect_provider(base_url: str, model: str) -> str:
    """从 base_url 或 model name 自动推测 provider。"""
    for prov, info in PROVIDER_CONFIGS.items():
        if info["base_url"] in base_url:
            return prov
        if model in info["models"]:
            return prov
    return "minimax"


def get_llm(api_key: str, base_url: str = "", model: str = "") -> BaseLLM:
    """临时构造 LLM(用于测试)。自动从 base_url 或 model 名检测 provider。"""
    provider = _detect_provider(base_url, model)
    adapter_cls = _PROVIDER_ADAPTERS.get(provider, MiniMaxLLM)
    return adapter_cls(
        api_key=api_key,
        base_url=base_url or PROVIDER_CONFIGS.get(provider, {}).get("base_url", ""),
        model=model or "",
    )
