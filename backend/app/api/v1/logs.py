"""Logs API — 操作日志。"""
from __future__ import annotations
from fastapi import APIRouter
from app.db.database import query, execute
from app.api.v1 import router as v1_router


router = APIRouter(prefix="/logs", tags=["logs"])
v1_router.include_router(router)


@router.get("")
def list_logs(limit: int = 100, offset: int = 0):
    rows = query("SELECT * FROM operation_logs ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))
    return {"ok": True, "data": [dict(r) for r in rows]}


@router.post("")
def add_log(payload: dict):
    import time
    action = payload.get("action", "")
    target = payload.get("target", "")
    detail = payload.get("detail", "")
    execute(
        "INSERT INTO operation_logs (action, target, detail, created_at) VALUES (?, ?, ?, ?)",
        (action, target, detail, int(time.time())),
    )
    return {"ok": True}