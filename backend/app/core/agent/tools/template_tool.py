"""模板库 Tool — 查询 / 预览文书模板。"""
from __future__ import annotations
from app.core.agent.tool import BaseTool, ToolSpec, ToolResult
from app.services.template_service import list_templates, render_template as render_preview


class TemplateListTool(BaseTool):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="template_list",
            description="列出可用的法律文书模板（起诉状、答辩状、代理词、合同、律师函等）",
            parameters={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "按类别筛选",
                        "enum": ["起诉状", "答辩状", "代理词", "上诉状", "合同", "律师函"],
                    },
                },
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        try:
            templates = list_templates(category=kwargs.get("category"))
            return ToolResult(success=True, data=[{
                "id": t["id"],
                "name": t.get("name", ""),
                "category": t.get("category", ""),
                "description": t.get("description", ""),
                "variables": t.get("variables", []),
            } for t in (templates or [])])
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class TemplatePreviewTool(BaseTool):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="template_preview",
            description="预览模板渲染效果（填入变量后的文书样稿）",
            parameters={
                "type": "object",
                "properties": {
                    "template_id": {"type": "integer", "description": "模板 ID"},
                    "variables": {
                        "type": "object",
                        "description": "模板变量键值对",
                        "additionalProperties": {"type": "string"},
                    },
                },
                "required": ["template_id"],
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        template_id = kwargs.get("template_id")
        if not template_id:
            return ToolResult(success=False, error="template_id 不能为空")
        try:
            preview = render_preview(template_id, kwargs.get("variables", {}))
            return ToolResult(success=True, data=preview)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
