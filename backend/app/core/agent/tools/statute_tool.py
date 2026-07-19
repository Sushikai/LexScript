"""法条检索 Tool。"""
from __future__ import annotations
from app.core.agent.tool import BaseTool, ToolSpec, ToolResult
from app.services.statute_service import search_statutes, list_categories, find_citations


class StatuteSearchTool(BaseTool):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="statute_search",
            description="检索法律法规条目（民法典、刑法、公司法等），按关键词或法条编号查找",
            parameters={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "关键词或法条编号"},
                    "category": {
                        "type": "string",
                        "description": "法条类别筛选",
                        "enum": [
                            "民法典", "刑法", "行政法", "诉讼法", "公司法",
                            "合同法", "知识产权法", "劳动法", "婚姻家庭法",
                            "物权法", "侵权责任法", "商法", "国际法",
                        ],
                    },
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["keyword"],
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        keyword = kwargs.get("keyword", "")
        if not keyword:
            return ToolResult(success=False, error="keyword 不能为空")
        try:
            results = search_statutes(keyword, category=kwargs.get("category"))
            limit = kwargs.get("limit", 10)
            return ToolResult(success=True, data=[{
                "code": r.get("code", ""),
                "name": r.get("name", ""),
                "category": r.get("category", ""),
                "content": r.get("content", "")[:500],
            } for r in (results or [])[:limit]])
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class StatuteCategoriesTool(BaseTool):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="statute_categories",
            description="列出所有法条类别",
            parameters={"type": "object", "properties": {}},
        )

    async def execute(self, **kwargs) -> ToolResult:
        try:
            cats = list_categories()
            return ToolResult(success=True, data=cats)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class StatuteCitationTool(BaseTool):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="statute_citations",
            description="从卷宗/案情描述文本中检测法条引用（第XX条、《民法典》第X条等），返回最新版本的法条内容",
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "包含法条引用的文本"},
                },
                "required": ["text"],
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        text = kwargs.get("text", "")
        if not text:
            return ToolResult(success=False, error="text 不能为空")
        try:
            citations = find_citations(text)
            return ToolResult(success=True, data=citations)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
