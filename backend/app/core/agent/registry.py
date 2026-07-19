"""Tool 注册中心 — 所有工具在此注册，LLM 通过 Function Calling 调用。"""
from __future__ import annotations
import time
from typing import Any
from loguru import logger
from .tool import BaseTool, ToolResult


class ToolRegistry:
    """全局 Tool 注册表。"""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        self._call_history: list[dict] = []

    def register(self, tool: BaseTool):
        """注册一个 Tool。"""
        name = tool.spec.name
        if name in self._tools:
            logger.warning(f"[registry] Tool {name} 已存在，覆盖")
        self._tools[name] = tool
        logger.info(f"[registry] ✓ Tool 注册: {name}")

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    @property
    def all_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def openai_tools(self) -> list[dict[str, Any]]:
        """返回所有工具的 OpenAI Function Calling 格式。"""
        return [t.to_openai_tool() for t in self._tools.values()]

    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    async def call_tool(self, name: str, **kwargs) -> ToolResult:
        """按名称调用 Tool（含超时与日志）。"""
        tool = self.get(name)
        if not tool:
            return ToolResult(success=False, error=f"Tool '{name}' 不存在")
        t0 = time.time()
        try:
            result = await tool.execute(**kwargs)
            elapsed = (time.time() - t0) * 1000
            self._call_history.append({
                "tool": name,
                "args": kwargs,
                "success": result.success,
                "elapsed_ms": round(elapsed, 1),
            })
            if not result.success:
                logger.warning(f"[registry] Tool {name} 失败: {result.error}")
            return result
        except Exception as e:
            elapsed = (time.time() - t0) * 1000
            logger.error(f"[registry] Tool {name} 异常: {e}")
            return ToolResult(success=False, error=str(e))

    async def call_tools_from_llm(
        self, tool_calls: list[dict] | None
    ) -> list[dict[str, Any]]:
        """解析 LLM 返回的 tool_calls 并并发执行独立工具。"""
        if not tool_calls:
            return []

        async def _execute_one(tc: dict) -> dict:
            name = tc.get("function", {}).get("name", "")
            try:
                import json
                args_raw = tc.get("function", {}).get("arguments", "{}")
                args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
            except json.JSONDecodeError:
                args = {}
            result = await self.call_tool(name, **args)
            return {
                "tool_call_id": tc.get("id", ""),
                "tool_name": name,
                "result": result.data if result.success else {"error": result.error},
                "success": result.success,
            }

        import asyncio
        results = await asyncio.gather(*[_execute_one(tc) for tc in tool_calls])
        return list(results)

    def get_stats(self) -> dict:
        """工具调用统计。"""
        total = len(self._call_history)
        success = sum(1 for c in self._call_history if c["success"])
        return {
            "total_calls": total,
            "success_calls": success,
            "fail_calls": total - success,
            "tools_registered": len(self._tools),
            "tools": self.tool_names(),
        }


# 全局单例
registry = ToolRegistry()
