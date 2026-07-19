"""Search API — 语义/关键词/混合检索。"""
from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.services import vector_service
from app.services.config_service import get_config
from app.core.auth import get_current_user
from app.api.v1 import router as v1_router


router = APIRouter(prefix="/search", tags=["search"])
v1_router.include_router(router)


class SearchReq(BaseModel):
    query: str
    mode: str = "hybrid"  # semantic | keyword | hybrid
    top_k: int = 20
    file_id: int | None = None


def _enrich_result(r: dict) -> dict:
    """为搜索结果增加 _source_type / _source_name 等标注字段。"""
    out = dict(r)
    meta = r.get("metadata") or {}
    file_id = r.get("file_id") or meta.get("file_id")
    file_name = r.get("file_name") or meta.get("file_name")
    doc_uuid = r.get("doc_uuid") or meta.get("doc_uuid")
    title = r.get("title") or meta.get("title")
    out["file_id"] = int(file_id) if file_id else None
    out["file_name"] = file_name or ""
    out["_source_name"] = file_name or title or "未知来源"
    if doc_uuid:
        out["_source_type"] = "document"
        out["_source_name"] = title or "法律文书"
    elif file_id:
        out["_source_type"] = "file"
    else:
        out["_source_type"] = "chunk"
    return out


@router.post("")
def search(req: SearchReq, user: dict = Depends(get_current_user)):
    api_key = get_config("llm_api_key") or get_config("minimax_api_key") or ""
    where = {"file_id": str(req.file_id)} if req.file_id else None

    if req.mode == "semantic":
        results = vector_service.search_semantic(req.query, api_key=api_key, top_k=req.top_k, where=where)
    elif req.mode == "keyword":
        results = vector_service.search_by_keyword(req.query, top_k=req.top_k, file_id=req.file_id)
    else:
        results = vector_service.search_hybrid(req.query, api_key=api_key, top_k=req.top_k, where=where)
    return {"ok": True, "data": [_enrich_result(r) for r in results]}


@router.post("/hybrid")
def search_hybrid(req: SearchReq, user: dict = Depends(get_current_user)):
    """快速混合检索 (mode=hybrid 的快捷入口)."""
    api_key = get_config("llm_api_key") or get_config("minimax_api_key") or ""
    where = {"file_id": str(req.file_id)} if req.file_id else None
    results = vector_service.search_hybrid(req.query, api_key=api_key, top_k=req.top_k, where=where)
    return {"ok": True, "data": results}


@router.post("/by-statute")
def search_by_statute(req: SearchReq, user: dict = Depends(get_current_user)):
    """按法条号反查引用文书。"""
    from app.db.database import query
    rows = query(
        "SELECT id, uuid, title, doc_type, content, created_at FROM documents WHERE statutes LIKE ?",
        (f"%{req.query}%",),
    )
    return {"ok": True, "data": [dict(r) for r in rows]}