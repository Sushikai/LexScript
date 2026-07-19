"""Statutes API — 法条检索 / 语义搜索 / 批量导入。"""
from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from app.services import statute_service
from app.api.v1 import router as v1_router


router = APIRouter(prefix="/statutes", tags=["statutes"])
v1_router.include_router(router)


class StatuteSearchReq(BaseModel):
    keyword: str
    category: str | None = None
    limit: int = 20


class StatuteUpsertReq(BaseModel):
    code: str
    name: str
    category: str
    content: str
    source: str | None = None


class SemanticSearchReq(BaseModel):
    query: str
    top_k: int = 10


class BulkImportReq(BaseModel):
    directory: str | None = None


@router.post("/search")
def search_statutes(req: StatuteSearchReq):
    """关键词搜索法条。"""
    results = statute_service.search_statutes(req.keyword, req.category, req.limit)
    return {"ok": True, "data": results}


@router.post("/semantic-search")
def semantic_search(req: SemanticSearchReq):
    """语义搜索法条（向量嵌入）。"""
    results = statute_service.semantic_search(req.query, req.top_k)
    return {"ok": True, "data": results}


@router.post("/hybrid-search")
def hybrid_search(req: StatuteSearchReq):
    """混合搜索：语义 + 关键词。"""
    results = statute_service.hybrid_search(req.keyword, req.category, req.limit)
    return {"ok": True, "data": results}


@router.get("/categories")
def list_categories():
    """获取法条分类列表。"""
    return {"ok": True, "data": statute_service.list_categories()}


@router.post("/upsert")
def upsert_statute(req: StatuteUpsertReq):
    """录入或更新法条。"""
    s = statute_service.upsert_statute(req.code, req.name, req.category, req.content, req.source)
    return {"ok": True, "data": s}


@router.get("/{code}")
def get_statute(code: str):
    """获取单条法条详情。"""
    s = statute_service.get_statute(code)
    if not s:
        return {"ok": False, "code": "NOT_FOUND", "message": "法条不存在"}
    return {"ok": True, "data": s}


@router.post("/sync")
def sync_statutes():
    """从 flk.npc.gov.cn 在线同步最新法条（首次全量，后续增量）。"""
    from app.services.statute_service import sync_from_online
    result = sync_from_online()
    return {"ok": True, "data": result}


@router.post("/index-vector")
def index_vector():
    """将所有法条索引入向量库（语义搜索用）。"""
    result = statute_service.build_vector_index()
    return {"ok": True, "data": result}


@router.post("/bulk-import")
def bulk_import(req: BulkImportReq):
    """从 KB 目录批量导入法条。"""
    result = statute_service.bulk_import_from_directory(req.directory)
    return {"ok": True, "data": result}


@router.post("/bulk-import-file")
def bulk_import_file(req: BulkImportReq):
    """从单个文件导入法条。"""
    if not req.directory:
        return {"ok": False, "code": "NO_PATH", "message": "请提供文件路径"}
    result = statute_service.bulk_import_from_text(req.directory)
    return {"ok": True, "data": result}
