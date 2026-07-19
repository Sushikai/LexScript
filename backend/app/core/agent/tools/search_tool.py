"""智能检索 Tool — 语义 / 关键词 / 混合检索。"""
from __future__ import annotations
from app.core.agent.tool import BaseTool, ToolSpec, ToolResult
from app.services.vector_service import search_hybrid, search_semantic, search_by_keyword


class HybridSearchTool(BaseTool):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="search_hybrid",
            description="混合检索（向量语义 + 关键词 BM25），从已索引的卷宗中查找相关内容",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词或自然语言描述"},
                    "top_k": {"type": "integer", "description": "返回结果数", "default": 10},
                    "file_id": {"type": "integer", "description": "限定在某个文件中搜索（可选）"},
                },
                "required": ["query"],
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        query = kwargs.get("query", "")
        if not query:
            return ToolResult(success=False, error="query 不能为空")
        try:
            results = search_hybrid(query, top_k=kwargs.get("top_k", 10))
            return ToolResult(success=True, data=[{
                "score": round(r.get("score", 0), 4),
                "content": r.get("content", "")[:500],
                "file": r.get("file_name", ""),
                "chunk_index": r.get("chunk_index"),
            } for r in (results or [])])
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class SemanticSearchTool(BaseTool):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="search_semantic",
            description="纯语义向量检索，用自然语言查找语义相似的内容",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "自然语言查询"},
                    "top_k": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        try:
            results = search_semantic(kwargs.get("query", ""), top_k=kwargs.get("top_k", 10))
            return ToolResult(success=True, data=results)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
