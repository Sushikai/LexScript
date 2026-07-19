"""Tasks API — 异步任务进度。"""
from __future__ import annotations
from fastapi import APIRouter
from app.db.database import query, query_one
from app.api.v1 import router as v1_router


router = APIRouter(prefix="/tasks", tags=["tasks"])
v1_router.include_router(router)


@router.get("/{uuid}")
def get_task(uuid: str):
    row = query_one("SELECT * FROM async_tasks WHERE uuid = ?", (uuid,))
    if not row:
        return {"ok": False, "code": "NOT_FOUND", "message": "任务不存在"}
    return {"ok": True, "data": dict(row)}


@router.get("")
def list_tasks(limit: int = 50, offset: int = 0):
    rows = query("SELECT * FROM async_tasks ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))
    return {"ok": True, "data": [dict(r) for r in rows]}


@router.delete("/{uuid}")
def cancel_task(uuid: str):
    from app.db.database import execute
    execute("UPDATE async_tasks SET status = 'cancelled' WHERE uuid = ?", (uuid,))
    return {"ok": True, "data": {"uuid": uuid}}