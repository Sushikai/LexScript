"""Chat API — SSE 流式对话 + 会话管理。"""
from __future__ import annotations
import json
from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.services import chat_service
from app.core.auth import get_current_user
from app.core.llm.registry import list_models, list_providers
from app.api.v1 import router as v1_router


router = APIRouter(prefix="/chat", tags=["chat"])
v1_router.include_router(router)


class CreateSessionReq(BaseModel):
    title: str = "新对话"
    role: str = "legal_expert"
    session_type: str = "normal"
    model: str = ""


class SendMessageReq(BaseModel):
    content: str
    scene: str | None = None  # case_overview | document_generation | compliance_check | evidence_analysis


@router.post("/sessions")
def create_session(req: CreateSessionReq, user: dict = Depends(get_current_user)):
    sess = chat_service.create_session(
        title=req.title, role=req.role,
        session_type=req.session_type, model=req.model,
        owner_user_id=user["id"],
    )
    return {"ok": True, "data": sess}


@router.get("/sessions")
def list_sessions(limit: int = 50, offset: int = 0, user: dict = Depends(get_current_user)):
    sessions = chat_service.list_sessions(limit=limit, offset=offset, user_id=user["id"])
    return {"ok": True, "data": sessions}


@router.get("/sessions/{uuid}")
def get_session(uuid: str, user: dict = Depends(get_current_user)):
    sess = chat_service.get_session_by_uuid(uuid)
    if not sess:
        return {"ok": False, "code": "NOT_FOUND", "message": "会话不存在"}
    if sess.get("owner_user_id") and sess["owner_user_id"] != user["id"] :
        return {"ok": False, "code": "FORBIDDEN", "message": "无权访问"}
    msgs = chat_service.list_messages(sess["id"])
    return {"ok": True, "data": {"session": sess, "messages": msgs}}


@router.patch("/sessions/{uuid}")
def update_session(uuid: str, payload: dict, user: dict = Depends(get_current_user)):
    sess = chat_service.get_session_by_uuid(uuid)
    if sess and sess.get("owner_user_id") and sess["owner_user_id"] != user["id"] :
        return {"ok": False, "code": "FORBIDDEN", "message": "无权修改"}
    sess = chat_service.update_session(uuid, **payload)
    if not sess:
        return {"ok": False, "code": "NOT_FOUND", "message": "会话不存在"}
    return {"ok": True, "data": sess}


@router.delete("/sessions/{uuid}")
def delete_session(uuid: str, user: dict = Depends(get_current_user)):
    sess = chat_service.get_session_by_uuid(uuid)
    if sess and sess.get("owner_user_id") and sess["owner_user_id"] != user["id"] :
        return {"ok": False, "code": "FORBIDDEN", "message": "无权删除"}
    chat_service.delete_session(uuid)
    return {"ok": True, "data": {"uuid": uuid}}


@router.post("/sessions/{uuid}/messages")
async def send_message(uuid: str, req: SendMessageReq, request: Request, user: dict = Depends(get_current_user)):
    """SSE 流式返回。"""
    sess = chat_service.get_session_by_uuid(uuid)
    if sess and sess.get("owner_user_id") and sess["owner_user_id"] != user["id"] :
        return {"ok": False, "code": "FORBIDDEN", "message": "无权访问"}
    return StreamingResponse(
        chat_service.stream_chat(uuid, req.content, scene=req.scene),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/models")
def chat_models():
    """返回可用模型列表。"""
    return {"ok": True, "data": {"providers": list_providers(), "models": list_models()}}


@router.get("/roles")
def list_roles():
    from app.config import ROLE_PRESETS
    return {"ok": True, "data": ROLE_PRESETS}