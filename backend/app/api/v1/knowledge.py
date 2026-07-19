"""Knowledge Base API — 知识库管理 / 文件操作 / REG 工程化。"""
from __future__ import annotations
import os
from fastapi import APIRouter, UploadFile, File, Form, Depends
from pydantic import BaseModel
from app.core.auth import get_current_user
from app.api.v1 import router as v1_router
from app.services import knowledge_service as kb

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
v1_router.include_router(router)


class SetPathReq(BaseModel):
    path: str


class WriteFileReq(BaseModel):
    content: str


class CreateFileReq(BaseModel):
    name: str
    content: str = ""


@router.get("/status")
def kb_status():
    """知识库概览：路径 / 文件数 / 状态统计。"""
    return {"ok": True, "data": kb.get_kb_status()}


@router.get("/path")
def kb_path():
    """获取当前 KB 路径。"""
    return {"ok": True, "data": {"path": kb.get_kb_path()}}


@router.post("/path")
def set_kb_path(req: SetPathReq):
    """设置 KB 路径。"""
    p = kb.set_kb_path(req.path)
    return {"ok": True, "data": {"path": p}}


@router.get("/files")
def list_files(status: str | None = None):
    """列出 KB 中已注册文件。"""
    return {"ok": True, "data": kb.list_kb_files(status)}


@router.get("/disk")
def list_disk():
    """列出 KB 目录实际文件（含注册状态）。"""
    return {"ok": True, "data": kb.list_kb_on_disk()}


@router.post("/import")
def import_files():
    """扫描 KB 目录导入所有文件。"""
    results = kb.import_all_kb_files()
    return {"ok": True, "data": {"imported": len(results), "files": results}}


@router.post("/reg/{file_id}")
def reg_file(file_id: int):
    """对单个文件执行 REG（解析 → 分片 → 向量索引）。"""
    try:
        result = kb.reg_file(file_id)
        return {"ok": True, "data": result}
    except Exception as e:
        return {"ok": False, "code": "REG_FAILED", "message": str(e)}


@router.post("/reindex/{file_id}")
def reindex_file(file_id: int):
    """强制重新索引（先重置状态再 REG）。"""
    try:
        from app.db.database import execute
        execute("UPDATE files SET status = 'pending', error = NULL WHERE id = ?", (file_id,))
        result = kb.reg_file(file_id)
        return {"ok": True, "data": result}
    except Exception as e:
        return {"ok": False, "code": "REINDEX_FAILED", "message": str(e)}


@router.post("/retry-failed")
def retry_failed():
    """重试所有失败的文件。"""
    try:
        from app.db.database import execute
        execute("UPDATE files SET status = 'pending', error = NULL WHERE status = 'failed'")
        results = kb.reg_all_pending()
        return {"ok": True, "data": {"total": len(results), "results": results}}
    except Exception as e:
        return {"ok": False, "code": "RETRY_FAILED", "message": str(e)}


@router.post("/reg-all")
def reg_all():
    """对所有未索引文件执行 REG。"""
    results = kb.reg_all_pending()
    return {"ok": True, "data": {"total": len(results), "results": results}}


@router.get("/read/{file_id}")
def read_file(file_id: int):
    """读取文件内容。"""
    try:
        return {"ok": True, "data": kb.read_file_content(file_id)}
    except Exception as e:
        return {"ok": False, "code": "NOT_FOUND", "message": str(e)}


@router.post("/write/{file_id}")
def write_file(file_id: int, req: WriteFileReq):
    """写入文件内容（写入后需重新 REG）。"""
    try:
        return {"ok": True, "data": kb.write_file_content(file_id, req.content)}
    except Exception as e:
        return {"ok": False, "code": "WRITE_FAILED", "message": str(e)}


@router.post("/create")
def create_file(req: CreateFileReq):
    """在 KB 目录创建新文件。"""
    try:
        return {"ok": True, "data": kb.create_file_in_kb(req.name, req.content)}
    except Exception as e:
        return {"ok": False, "code": "CREATE_FAILED", "message": str(e)}


@router.delete("/delete/{file_id}")
def delete_file(file_id: int):
    """删除文件记录及向量。"""
    kb.delete_file_from_kb(file_id)
    return {"ok": True, "data": {"deleted": file_id}}


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传文件到 KB 目录。"""
    kb_path = kb.get_kb_path()
    dest = os.path.join(kb_path, file.filename or "unnamed")
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)
    result = kb.import_file(dest)
    return {"ok": True, "data": result}


@router.post("/rescan")
def rescan():
    """重新扫描 KB 目录，导入新文件。"""
    results = kb.import_all_kb_files()
    return {"ok": True, "data": {"imported": len(results)}}
