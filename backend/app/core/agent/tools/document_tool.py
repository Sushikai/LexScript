"""文书生成与管理 Tool。"""
from __future__ import annotations
from app.core.agent.tool import BaseTool, ToolSpec, ToolResult
from app.services.document_generator import generate_document
from app.api.v1.documents import list_documents, get_document


class DocumentGenerateTool(BaseTool):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="document_generate",
            description="一键生成法律文书：读卷宗 → 向量检索 → 法条匹配 → AI 生成",
            parameters={
                "type": "object",
                "properties": {
                    "case_name": {"type": "string", "description": "案件名称"},
                    "doc_type": {
                        "type": "string",
                        "enum": ["起诉状", "答辩状", "代理词", "上诉状", "合同", "律师函", "裁定书"],
                        "description": "文书类型",
                    },
                    "file_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "参考的卷宗文件 ID 列表",
                    },
                    "extra_requirements": {
                        "type": "string",
                        "description": "额外的生成要求或特殊说明",
                    },
                },
                "required": ["case_name", "doc_type"],
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        try:
            result = generate_document(
                case_name=kwargs.get("case_name", ""),
                doc_type=kwargs.get("doc_type", "起诉状"),
                file_ids=kwargs.get("file_ids", []),
                extra_requirements=kwargs.get("extra_requirements", ""),
            )
            return ToolResult(success=True, data={
                "uuid": result.get("uuid", ""),
                "title": result.get("title", ""),
                "content": result.get("content", "")[:2000],
                "doc_type": result.get("doc_type", ""),
                "statutes": result.get("statutes", []),
            })
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class DocumentListTool(BaseTool):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="document_list",
            description="列出已生成的文书",
            parameters={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 20},
                    "doc_type": {"type": "string", "description": "按文书类型筛选"},
                },
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        try:
            docs = list_documents(kwargs.get("doc_type"))
            limit = kwargs.get("limit", 20)
            return ToolResult(success=True, data=[{
                "uuid": d["uuid"],
                "title": d.get("title", ""),
                "doc_type": d.get("doc_type", ""),
                "created": str(d.get("created_at", "")),
            } for d in (docs or [])[:limit]])
        except Exception as e:
            return ToolResult(success=False, error=str(e))
