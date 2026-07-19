"""文件管理 Tool — 导入 / 解析 / 列表 / 搜索文件。"""
from __future__ import annotations
from app.core.agent.tool import BaseTool, ToolSpec, ToolResult
from app.services.file_service import (
    list_files,
    import_file,
    delete_file,
    parse_file as _parse_file,
)


class FileListTool(BaseTool):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="file_list",
            description="列出已导入的文件 / 卷宗，支持按文件夹、文件类型、状态筛选",
            parameters={
                "type": "object",
                "properties": {
                    "folder_id": {"type": "integer", "description": "按案件文件夹筛选（可选）"},
                    "mime": {"type": "string", "description": "按文件类型筛选，如 application/pdf"},
                    "status": {"type": "string", "description": "按状态筛选: imported/parsed/indexed/failed"},
                    "limit": {"type": "integer", "description": "返回条数上限", "default": 20},
                },
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        try:
            files = list_files(kwargs.get("folder_id"), kwargs.get("mime"), kwargs.get("status"))
            limit = kwargs.get("limit", 20)
            return ToolResult(success=True, data=[{
                "id": f["id"],
                "name": f["name"],
                "size": f["size"],
                "type": f["mime"],
                "status": f["status"],
                "chunks": f.get("chunk_count", 0),
                "created": str(f.get("created_at", "")),
            } for f in (files or [])[:limit]])
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class FileImportTool(BaseTool):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="file_import",
            description="从本地路径导入文件或目录，自动解析支持的格式（PDF/DOCX/Excel/图片/文本）",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件或目录的本地绝对路径"},
                    "folder_id": {"type": "integer", "description": "导入到指定案件文件夹（可选）"},
                    "recursive": {"type": "boolean", "description": "是否递归导入子目录", "default": True},
                },
                "required": ["path"],
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs.get("path", "")
        if not path:
            return ToolResult(success=False, error="path 不能为空")
        try:
            result = import_file(path, kwargs.get("folder_id"), kwargs.get("recursive", True))
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class FileParseTool(BaseTool):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="file_parse",
            description="解析已导入的文件（分片 + 向量化索引），使其可被检索",
            parameters={
                "type": "object",
                "properties": {
                    "file_id": {"type": "integer", "description": "文件 ID"},
                },
                "required": ["file_id"],
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        file_id = kwargs.get("file_id")
        if not file_id:
            return ToolResult(success=False, error="file_id 不能为空")
        try:
            result = _parse_file(file_id)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
