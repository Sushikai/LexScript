"""Templates API — 模板 CRUD + 预览。"""
from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from app.services import template_service
from app.api.v1 import router as v1_router


router = APIRouter(prefix="/templates", tags=["templates"])
v1_router.include_router(router)


class TemplateCreateReq(BaseModel):
    name: str
    category: str
    content: str
    variables: str = "[]"
    description: str = ""


class PreviewReq(BaseModel):
    variables: dict = {}


@router.get("")
def list_templates(category: str | None = None):
    templates = template_service.list_templates(category)
    return {"ok": True, "data": templates}


@router.post("")
def create_template(req: TemplateCreateReq):
    t = template_service.create_template(req.name, req.category, req.content, req.variables, req.description)
    return {"ok": True, "data": t}


@router.get("/builtins")
def get_builtins():
    """内置模板列表。"""
    return {"ok": True, "data": template_service.get_builtin_templates()}


@router.get("/{tid}")
def get_template(tid: int):
    t = template_service.get_template(tid)
    if not t:
        return {"ok": False, "code": "NOT_FOUND", "message": "模板不存在"}
    return {"ok": True, "data": t}


@router.patch("/{tid}")
def update_template(tid: int, payload: dict):
    t = template_service.update_template(tid, **payload)
    if not t:
        return {"ok": False, "code": "NOT_FOUND", "message": "模板不存在"}
    return {"ok": True, "data": t}


@router.delete("/{tid}")
def delete_template(tid: int):
    template_service.delete_template(tid)
    return {"ok": True, "data": {"id": tid}}


@router.post("/{tid}/preview")
def preview_template(tid: int, req: PreviewReq):
    try:
        html = template_service.render_template(tid, req.variables)
        return {"ok": True, "data": {"content": html}}
    except Exception as e:
        return {"ok": False, "code": "RENDER_ERROR", "message": str(e)}