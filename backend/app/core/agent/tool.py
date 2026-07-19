"""
Agent Tool 抽象基类。

每个 Tool 代表 LLM 可以调用的一个能力:
  - FileTool: 文件导入/解析/搜索
  - SearchTool: 语义/关键词混合检索
  - DocumentTool: 文书生成/管理
  - TemplateTool: 模板查询/预览
  - StatuteTool: 法条检索
  - ...
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolSpec:
    """Tool 的 OpenAI Function Calling Schema。"""
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


@dataclass
class ToolResult:
    """Tool 执行结果。"""
    success: bool
    data: Any = None
    error: str | None = None
    context: dict[str, Any] = field(default_factory=dict)


class BaseTool(ABC):
    """所有 Agent Tool 的基类。"""

    @property
    @abstractmethod
    def spec(self) -> ToolSpec:
        """OpenAI Function Calling 格式的 Tool 定义。"""

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """执行 Tool 调用。"""

    def to_openai_tool(self) -> dict[str, Any]:
        """转为 OpenAI / MiniMax Function Calling 格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.spec.name,
                "description": self.spec.description,
                "parameters": self.spec.parameters,
            },
        }
