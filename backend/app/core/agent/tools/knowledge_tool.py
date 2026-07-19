"""知识库 Agent Tools — 通过 AI 对话框读写文件 / REG 工程化 / 检索。"""
from __future__ import annotations
import json
from app.core.agent.tool import BaseTool, ToolSpec, ToolResult
from app.services import knowledge_service as kb


class KbListTool(BaseTool):
    """列出知识库中的文件及其 REG 状态。"""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="knowledge_list",
            description="列出知识库中的所有文件，包括 REG 状态（pending/indexed/failed）",
            parameters={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "按状态筛选: pending / indexed / failed",
                        "default": "",
                    },
                },
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        try:
            files = kb.list_kb_files(kwargs.get("status") or None)
            return ToolResult(success=True, data=[{
                "id": f["id"],
                "name": f["name"],
                "size": f["size"],
                "status": f["status"],
                "chunks": f.get("chunk_count", 0),
                "updated": str(f.get("updated_at", "")),
            } for f in files])
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class KbReadTool(BaseTool):
    """读取知识库中某个文件的内容。"""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="knowledge_read",
            description="读取知识库中指定文件的内容（文本格式），用于让 AI 分析文件内容",
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
            data = kb.read_file_content(file_id)
            return ToolResult(success=True, data=data)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class KbWriteTool(BaseTool):
    """写入内容到知识库中的文件（AI 直接输出文件）。"""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="knowledge_write",
            description="写入内容到知识库中的现有文件（覆盖写入）。写入后文件会被标记为 pending，需要重新 REG",
            parameters={
                "type": "object",
                "properties": {
                    "file_id": {"type": "integer", "description": "文件 ID"},
                    "content": {"type": "string", "description": "要写入的文件内容"},
                },
                "required": ["file_id", "content"],
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        file_id = kwargs.get("file_id")
        content = kwargs.get("content", "")
        if not file_id:
            return ToolResult(success=False, error="file_id 不能为空")
        try:
            data = kb.write_file_content(file_id, content)
            return ToolResult(success=True, data=data)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class KbCreateFileTool(BaseTool):
    """在知识库中创建新文件。"""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="knowledge_create",
            description="在知识库中创建一个新文件，可指定文件名和内容。文件创建后自动导入",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "文件名（含扩展名，如 起诉状.md）"},
                    "content": {"type": "string", "description": "文件内容", "default": ""},
                },
                "required": ["name"],
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        name = kwargs.get("name", "")
        content = kwargs.get("content", "")
        if not name:
            return ToolResult(success=False, error="name 不能为空")
        try:
            data = kb.create_file_in_kb(name, content)
            return ToolResult(success=True, data=data)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class KbRegTool(BaseTool):
    """对指定文件执行 REG（解析 → 分片 → 向量反向索引）。"""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="knowledge_reg",
            description="对知识库中指定文件执行 REG 工程化（解析 → 分片 → 向量反向索引），完成后文件可被语义检索",
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
            result = kb.reg_file(file_id)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class KbRegAllTool(BaseTool):
    """一键 REG：对所有未索引文件执行工程化。"""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="knowledge_reg_all",
            description="一键 REG 工程化：对所有未索引（pending）的文件执行 解析 → 分片 → 向量反向索引",
            parameters={
                "type": "object",
                "properties": {},
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        try:
            results = kb.reg_all_pending()
            return ToolResult(success=True, data={
                "total": len(results),
                "indexed": sum(1 for r in results if r["status"] == "indexed"),
                "failed": sum(1 for r in results if r["status"] == "failed"),
                "details": results,
            })
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class KbSearchTool(BaseTool):
    """在知识库中语义搜索文件内容。"""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="knowledge_search",
            description="在知识库中搜索文件内容（语义向量检索 + BM25 混合），返回相关片段及来源文件",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "top_k": {"type": "integer", "description": "返回结果条数", "default": 10},
                },
                "required": ["query"],
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        query_text = kwargs.get("query", "")
        top_k = kwargs.get("top_k", 10)
        if not query_text:
            return ToolResult(success=False, error="query 不能为空")
        try:
            # 同时搜索知识库文件 + 法律文书
            from app.services.knowledge_service import search_all
            results = search_all(query_text, top_k=top_k)

            # 标注每条的来源
            for r in results:
                meta = r.get("metadata", {}) or {}
                source = meta.get("source", "file")
                r["_source"] = "文书" if source == "document" else "文件"

            return ToolResult(success=True, data=results)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class KbImportTool(BaseTool):
    """从 KB 目录导入新文件（扫描目录）。"""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="knowledge_import",
            description="扫描知识库目录，导入所有新文件到系统（需后续执行 REG 才能索引）",
            parameters={
                "type": "object",
                "properties": {},
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        try:
            results = kb.import_all_kb_files()
            return ToolResult(success=True, data={
                "imported": len(results),
                "new_files": [r for r in results if "error" not in r],
            })
        except Exception as e:
            return ToolResult(success=False, error=str(e))
