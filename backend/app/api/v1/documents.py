"""Documents API — 文书生成/管理/导出。"""
from __future__ import annotations
import json
import time
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from loguru import logger
from app.db.database import query, query_one, execute
from app.core.auth import get_current_user
from app.core.security import decrypt as _decrypt
from app.services import document_generator, template_service, export_service
from app.api.v1 import router as v1_router


router = APIRouter(prefix="/documents", tags=["documents"])
v1_router.include_router(router)


class GenerateReq(BaseModel):
    case_name: str
    file_ids: list[int] = []
    doc_type: str = "起诉状"
    template_id: int | None = None
    extra_requirements: str = ""


class SectionRegenReq(BaseModel):
    section_range: list[int]
    instruction: str


@router.post("/generate")
async def generate(req: GenerateReq, user: dict = Depends(get_current_user)):
    """一键生成(SSE 流式) — 事件: status, chunk, done, error。"""
    async def event_generator():
        try:
            async for event in document_generator.generate_document_stream(
                case_name=req.case_name,
                file_ids=req.file_ids,
                doc_type=req.doc_type,
                template_id=req.template_id,
                extra_requirements=req.extra_requirements,
                owner_user_id=user["id"],
            ):
                yield event
        except Exception as e:
            logger.error(f"[doc] generate stream error: {e}")
            yield {"event": "error", "data": json.dumps({"message": str(e)})}

    return EventSourceResponse(event_generator())


@router.post("/from-template")
async def from_template(payload: dict):
    """模板填充生成。"""
    tid = payload.get("template_id")
    variables = payload.get("variables", {})
    if not tid:
        return {"ok": False, "code": "VALIDATION", "message": "template_id 必填"}
    try:
        html = template_service.render_template(tid, variables)
        return {"ok": True, "data": {"content": html}}
    except Exception as e:
        return {"ok": False, "code": "RENDER_ERROR", "message": str(e)}


def _decrypt_doc(row: dict) -> dict:
    d = dict(row)
    if d.get("content"):
        d["content"] = _decrypt(d["content"]) or d["content"]
    return d


@router.get("")
def list_documents(
    case_name: str | None = None,
    limit: int = 50, offset: int = 0,
    user: dict = Depends(get_current_user),
):
    uid = user["id"]
    if case_name:
        rows = query(
            "SELECT * FROM documents WHERE owner_user_id = ? AND case_name LIKE ? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (uid, f"%{case_name}%", limit, offset),
        )
    else:
        rows = query(
            "SELECT * FROM documents WHERE owner_user_id = ? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (uid, limit, offset),
        )
    return {"ok": True, "data": [_decrypt_doc(r) for r in rows]}


@router.get("/{uuid}")
def get_document(uuid: str, user: dict = Depends(get_current_user)):
    row = query_one("SELECT * FROM documents WHERE uuid = ?", (uuid,))
    if not row:
        return {"ok": False, "code": "NOT_FOUND", "message": "文书不存在"}
    if row.get("owner_user_id") and row["owner_user_id"] != user["id"]:
        return {"ok": False, "code": "FORBIDDEN", "message": "无权访问"}
    return {"ok": True, "data": _decrypt_doc(row)}


@router.patch("/{uuid}")
def update_document(uuid: str, payload: dict, user: dict = Depends(get_current_user)):
    row = query_one("SELECT * FROM documents WHERE uuid = ?", (uuid,))
    if not row:
        return {"ok": False, "code": "NOT_FOUND", "message": "文书不存在"}
    if row.get("owner_user_id") and row["owner_user_id"] != user["id"]:
        return {"ok": False, "code": "FORBIDDEN", "message": "无权修改"}
    fields = {k: v for k, v in payload.items() if v is not None}
    if not fields:
        return {"ok": False, "code": "NO_CHANGE", "message": "无更新字段"}
    fields["updated_at"] = int(time.time())
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [uuid]
    execute(f"UPDATE documents SET {set_clause} WHERE uuid = ?", tuple(vals))
    row = query_one("SELECT * FROM documents WHERE uuid = ?", (uuid,))
    return {"ok": True, "data": dict(row)}


@router.delete("/{uuid}")
def delete_document(uuid: str, user: dict = Depends(get_current_user)):
    row = query_one("SELECT * FROM documents WHERE uuid = ?", (uuid,))
    if row and row.get("owner_user_id") and row["owner_user_id"] != user["id"]:
        return {"ok": False, "code": "FORBIDDEN", "message": "无权删除"}
    execute("DELETE FROM documents WHERE uuid = ?", (uuid,))
    return {"ok": True, "data": {"uuid": uuid}}


@router.post("/{uuid}/regenerate")
async def regenerate_document(uuid: str, req: GenerateReq, user: dict = Depends(get_current_user)):
    """全量重生成。"""
    return await generate(req, user=user)


@router.post("/{uuid}/regenerate-section")
def regenerate_section(uuid: str, req: SectionRegenReq, user: dict = Depends(get_current_user)):
    row = query_one("SELECT * FROM documents WHERE uuid = ?", (uuid,))
    if not row:
        return {"ok": False, "code": "NOT_FOUND", "message": "文书不存在"}
    if row.get("owner_user_id") and row["owner_user_id"] != user["id"]:
        return {"ok": False, "code": "FORBIDDEN", "message": "无权操作"}
    return {"ok": True, "data": {"message": "段落重生成功能(v0.2.0)", "section_range": req.section_range}}


@router.post("/{uuid}/cite-statutes")
def cite_statutes(uuid: str, user: dict = Depends(get_current_user)):
    row = query_one("SELECT * FROM documents WHERE uuid = ?", (uuid,))
    if not row:
        return {"ok": False, "code": "NOT_FOUND", "message": "文书不存在"}
    if row.get("owner_user_id") and row["owner_user_id"] != user["id"]:
        return {"ok": False, "code": "FORBIDDEN", "message": "无权操作"}
    return {"ok": True, "data": {"message": "法条自动标注(v0.2.0完整版)"}}


@router.post("/{uuid}/risk-scan")
def risk_scan(uuid: str, user: dict = Depends(get_current_user)):
    row = query_one("SELECT * FROM documents WHERE uuid = ?", (uuid,))
    if not row:
        return {"ok": False, "code": "NOT_FOUND", "message": "文书不存在"}
    if row.get("owner_user_id") and row["owner_user_id"] != user["id"]:
        return {"ok": False, "code": "FORBIDDEN", "message": "无权操作"}
    return {"ok": True, "data": {"message": "合规校验功能(v0.2.0完整版)"}}


@router.get("/{uuid}/export")
def export_document(uuid: str, fmt: str = "md", user: dict = Depends(get_current_user)):
    row = query_one("SELECT * FROM documents WHERE uuid = ?", (uuid,))
    if not row:
        return {"ok": False, "code": "NOT_FOUND", "message": "文书不存在"}
    if row.get("owner_user_id") and row["owner_user_id"] != user["id"]:
        return {"ok": False, "code": "FORBIDDEN", "message": "无权访问"}
    if fmt == "docx":
        path = export_service.export_to_docx(row["content"], title=row["title"])
    elif fmt == "pdf":
        path = export_service.export_to_pdf(row["content"], title=row["title"])
    else:
        path = export_service.export_to_markdown(row["content"], title=row["title"])
    return FileResponse(path, filename=f"{row['title']}.{fmt}")