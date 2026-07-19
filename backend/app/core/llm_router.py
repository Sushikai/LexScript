"""
AlphaGPT‑grade Smart Model Router — 场景感知模型路由。
根据任务类型、所需推理深度、上下文长度，自动选择最优模型。
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Callable
from app.core.llm.base import BaseLLM
from app.core.llm.registry import get_llm_from_config, PROVIDER_CONFIGS


@dataclass
class ModelProfile:
    """模型能力画像。"""
    provider: str
    model: str
    strength: int           # 1=fast, 2=balanced, 3=deep reasoning
    max_context: int        # 最大上下文 token
    supports_tools: bool    # Function Calling 支持
    cost_per_1k_in: float   # 相对成本
    cost_per_1k_out: float


# 各模型能力画像
MODEL_PROFILES: dict[str, ModelProfile] = {
    "deepseek-chat":       ModelProfile("deepseek",  "deepseek-chat",       3, 65536,  True,  0.5,  2.0),
    "deepseek-reasoner":   ModelProfile("deepseek",  "deepseek-reasoner",   3, 65536,  False, 1.0,  4.0),
    "MiniMax-M3":          ModelProfile("minimax",   "MiniMax-M3",          2, 131072, True,  1.0,  1.0),
    "MiniMax-M2":          ModelProfile("minimax",   "MiniMax-M2",          1, 8192,   True,  0.3,  0.3),
    "glm-4-plus":          ModelProfile("zhipu",     "glm-4-plus",          2, 131072, True,  1.0,  1.0),
    "qwen-plus":           ModelProfile("qwen",      "qwen-plus",           2, 131072, True,  0.5,  0.5),
}

# 场景 → 最小需求
SCENE_REQUIREMENTS: dict[str, dict] = {
    "quick_qa":           {"min_strength": 1, "min_context": 4096,  "needs_tools": False, "priority": "speed"},
    "legal_search":       {"min_strength": 1, "min_context": 8192,  "needs_tools": True,  "priority": "speed"},
    "case_analysis":      {"min_strength": 2, "min_context": 32768, "needs_tools": True,  "priority": "quality"},
    "doc_generation":     {"min_strength": 3, "min_context": 65536, "needs_tools": False, "priority": "quality"},
    "doc_review":         {"min_strength": 2, "min_context": 32768, "needs_tools": False, "priority": "quality"},
    "contract_review":    {"min_strength": 2, "min_context": 32768, "needs_tools": False, "priority": "quality"},
    "evidence_analysis":  {"min_strength": 2, "min_context": 32768, "needs_tools": True,  "priority": "quality"},
    "risk_scan":          {"min_strength": 2, "min_context": 16384, "needs_tools": False, "priority": "quality"},
    "statute_research":   {"min_strength": 2, "min_context": 16384, "needs_tools": True,  "priority": "quality"},
    "strategy_planning":  {"min_strength": 3, "min_context": 32768, "needs_tools": False, "priority": "quality"},
}


def detect_scene(query: str, user_role: str = "litigator") -> str:
    """
    从用户问题自动检测最适合的场景。
    使用关键词 + 模式匹配，无需额外 LLM 调用。
    """
    q = query.lower()

    # 工具调用类
    if any(k in q for k in ("搜索", "检索", "查", "找一下", "法条", "法规", "条款", "司法解释")):
        return "legal_search"
    if any(k in q for k in ("合同审查", "审合同", "合同风险", "审查合同")):
        return "contract_review"
    if any(k in q for k in ("证据", "举证", "质证", "证据清单")):
        return "evidence_analysis"
    if any(k in q for k in ("风险", "合规", "校验", "检查")):
        return "risk_scan"

    # 文书类
    if any(k in q for k in ("起诉状", "答辩状", "代理词", "上诉状", "申请书", "律师函",
                            "生成", "起草", "撰写", "写一份", "拟一份", "文书")):
        return "doc_generation"
    if any(k in q for k in ("审", "改", "修改", "润色", "校对", "修正")):
        return "doc_review"

    # 策略与分析类
    if any(k in q for k in ("策略", "诉讼策略", "方案", "怎么打", "怎么办", "建议",
                            "胜算", "把握", "起诉还是", "和解还是")):
        return "strategy_planning"
    if any(k in q for k in ("分析", "案情", "案件分析", "法律关系", "争议焦点", "梳理")):
        return "case_analysis"

    # 法条研究
    if any(k in q for k in ("研究", "适用", "理解", "解释", "认定", "如何认定")):
        return "statute_research"

    # 简短问题 → fast path
    if len(q) < 30:
        return "quick_qa"

    # 默认: 交给有工具能力的模型
    return "case_analysis"


class SmartRouter:
    """
    场景感知模型路由器。
    支持: 单模型直接路由、双模型协同路由。
    """

    def __init__(self):
        self._available: dict[str, BaseLLM] = {}
        self._profiles: dict[str, ModelProfile] = {}
        self._refresh()

    def _refresh(self):
        """从当前配置刷新可用模型列表。"""
        llm = get_llm_from_config()
        if llm and llm.api_key:
            key = f"{llm.name}:{llm.model}"
            self._available[key] = llm
            profile = MODEL_PROFILES.get(llm.model)
            if profile:
                self._profiles[key] = profile

    def get_llm(self) -> tuple[str, BaseLLM]:
        """返回最适合当前配置的 (scene, llm)。"""
        self._refresh()
        if not self._available:
            raise RuntimeError("未配置任何 LLM，请先在设置中配置 API Key")
        # 只有一个模型时直接返回
        if len(self._available) == 1:
            k, v = next(iter(self._available.items()))
            return ("general", v)
        return ("general", list(self._available.values())[0])

    def route(self, query: str, user_role: str = "litigator") -> tuple[str, BaseLLM | None, str]:
        """
        路由决策:
        - 返回 (scene, selected_llm, fallback_reason)
        - selected_llm 为 None 表示没有合适的模型
        """
        self._refresh()
        scene = detect_scene(query, user_role)
        req = SCENE_REQUIREMENTS.get(scene, SCENE_REQUIREMENTS["case_analysis"])

        # 评分所有可用模型
        scored = []
        for key, llm in self._available.items():
            profile = self._profiles.get(key)
            if not profile:
                continue
            # 硬约束检查
            if profile.strength < req["min_strength"]:
                continue
            if profile.max_context < req["min_context"]:
                continue
            if req["needs_tools"] and not profile.supports_tools:
                continue

            score = profile.strength * 10
            if req["priority"] == "speed":
                score += (10 - int(profile.cost_per_1k_in * 10))
            elif req["priority"] == "quality":
                score += profile.strength * 5

            scored.append((score, profile, key, llm))

        if not scored:
            # 无完美匹配，降级：忽略 tools 约束
            for key, llm in self._available.items():
                profile = self._profiles.get(key)
                if not profile:
                    continue
                if profile.strength < req["min_strength"]:
                    continue
                if profile.max_context < req["min_context"]:
                    continue
                score = profile.strength * 8
                scored.append((score, profile, key, llm))

        if not scored:
            # 最差降级：任意可用模型
            for key, llm in self._available.items():
                profile = self._profiles.get(key)
                if not profile:
                    continue
                scored.append((profile.strength * 5, profile, key, llm))

        if not scored:
            return (scene, None, "无可用模型")

        scored.sort(key=lambda x: -x[0])
        _, profile, key, llm = scored[0]
        reason = f"scene={scene}, model={profile.model}, strength={profile.strength}, priority={req['priority']}"
        return (scene, llm, reason)


# 全局单例
router = SmartRouter()
