"""Files API — 文件导入/管理/解析/索引。"""
from __future__ import annotations
import json
import os
from fastapi import APIRouter, UploadFile, File, Form, Depends
from pydantic import BaseModel
from pathlib import Path
from app.services import file_service
from app.services.vector_service import search_hybrid, search_by_keyword
from app.core.vector.store import store
from app.core.auth import get_current_user
from app.api.v1 import router as v1_router

# 持久化上传目录
UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


router = APIRouter(prefix="/files", tags=["files"])
v1_router.include_router(router)


class ImportPathReq(BaseModel):
    path: str
    folder_id: int | None = None


class FolderCreateReq(BaseModel):
    name: str
    root_path: str
    case_number: str | None = None
    description: str | None = None


# ── 文件夹 ──────────────────────────────
@router.post("/folders")
def create_folder(req: FolderCreateReq, user: dict = Depends(get_current_user)):
    folder = file_service.create_folder(
        req.name, req.root_path, req.case_number, req.description,
        owner_user_id=user["id"],
    )
    return {"ok": True, "data": folder}


@router.get("/folders")
def list_folders(user: dict = Depends(get_current_user)):
    return {"ok": True, "data": file_service.list_folders(user["id"])}


# ── 文件 ─────────────────────────────────
@router.post("/import")
def import_path(req: ImportPathReq, user: dict = Depends(get_current_user)):
    """导入本地路径(递归扫描)。"""
    if os.path.isfile(req.path):
        f = file_service.import_file(req.path, req.folder_id, owner_user_id=user["id"])
        return {"ok": True, "data": f}
    elif os.path.isdir(req.path):
        files = file_service.scan_directory(req.path, req.folder_id, owner_user_id=user["id"])
        return {"ok": True, "data": files, "count": len(files)}
    else:
        return {"ok": False, "code": "NOT_FOUND", "message": f"路径不存在: {req.path}"}


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    folder_id: int = Form(0),
    user: dict = Depends(get_current_user),
):
    """上传文件 multipart。"""
    if not file.filename:
        return {"ok": False, "code": "NO_FILENAME", "message": "文件名为空"}
    # 安全校验:防止路径穿越
    safe_name = os.path.basename(file.filename)
    # 文件类型白名单
    allowed_ext = ('.pdf', '.docx', '.doc', '.xlsx', '.xls', '.txt', '.md', '.csv', '.json', '.jpg', '.jpeg', '.png', '.bmp')
    ext = os.path.splitext(safe_name)[1].lower()
    if ext and ext not in allowed_ext:
        return {"ok": False, "code": "INVALID_TYPE", "message": f"不支持的文件类型: {ext}"}
    # 大小限制 50MB
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        return {"ok": False, "code": "FILE_TOO_LARGE", "message": "文件超过 50MB 限制"}
    path = str(UPLOAD_DIR / safe_name)
    with open(path, "wb") as f:
        f.write(content)
    result = file_service.import_file(path, folder_id if folder_id else None, owner_user_id=user["id"])
    return {"ok": True, "data": result}


@router.get("")
def list_files(
    folder_id: int | None = None, status: str | None = None,
    limit: int = 100, offset: int = 0,
    user: dict = Depends(get_current_user),
):
    files = file_service.list_files(folder_id, status, limit, offset,
                                     user_id=user["id"])
    return {"ok": True, "data": files}


@router.get("/{file_id}")
def get_file(file_id: int, user: dict = Depends(get_current_user)):
    f = file_service.get_file(file_id)
    if not f:
        return {"ok": False, "code": "NOT_FOUND", "message": "文件不存在"}
    # 数据隔离校验
    if f.get("owner_user_id") and f["owner_user_id"] != user["id"]:
        return {"ok": False, "code": "FORBIDDEN", "message": "无权访问"}
    return {"ok": True, "data": f}


@router.delete("/{file_id}")
def delete_file(file_id: int, user: dict = Depends(get_current_user)):
    f = file_service.get_file(file_id)
    if f and f.get("owner_user_id") and f["owner_user_id"] != user["id"]:
        return {"ok": False, "code": "FORBIDDEN", "message": "无权删除"}
    file_service.delete_file(file_id)
    return {"ok": True, "data": {"file_id": file_id}}


@router.post("/{file_id}/parse")
def parse_file(file_id: int, user: dict = Depends(get_current_user)):
    """解析 + 索引。"""
    f = file_service.get_file(file_id)
    if not f:
        return {"ok": False, "code": "NOT_FOUND", "message": "文件不存在"}
    if f.get("owner_user_id") and f["owner_user_id"] != user["id"]:
        return {"ok": False, "code": "FORBIDDEN", "message": "无权操作"}
    try:
        chunks = file_service.parse_file(file_id)
        # 自动向量化
        from app.services.config_service import get_config
        api_key = get_config("llm_api_key") or get_config("minimax_api_key") or ""
        if api_key:
            file_service.index_chunks_to_vector(file_id, api_key=api_key)
        return {"ok": True, "data": {"chunks": len(chunks)}}
    except Exception as e:
        return {"ok": False, "code": "PARSE_ERROR", "message": str(e)}


@router.get("/{file_id}/raw")
def get_file_raw(file_id: int, user: dict = Depends(get_current_user)):
    """获取文件原始内容（流式预览/下载）。"""
    from fastapi.responses import FileResponse, Response
    f = file_service.get_file(file_id)
    if not f:
        return {"ok": False, "code": "NOT_FOUND", "message": "文件不存在"}
    if f.get("owner_user_id") and f["owner_user_id"] != user["id"]:
        return {"ok": False, "code": "FORBIDDEN", "message": "无权访问"}
    path = f["path"]
    if not os.path.isfile(path):
        return {"ok": False, "code": "FILE_MISSING", "message": "文件已从磁盘移除"}
    mime = f["mime"] or "application/octet-stream"
    name = f["name"]
    # 文本类文件直接返回内容
    text_mimes = {"text/plain", "text/markdown", "text/csv", "application/json", "text/html", "text/x-python", "text/typescript", "text/yaml", "text/xml"}
    if mime in text_mimes:
        content = Path(path).read_bytes()
        return Response(content=content, media_type=f"{mime}; charset=utf-8",
                        headers={"Content-Disposition": f"inline; filename*=UTF-8''{name}"})
    return FileResponse(path, media_type=mime, filename=name,
                        headers={"Content-Disposition": f"inline; filename*=UTF-8''{name}"})


@router.get("/{file_id}/content")
def get_file_content(file_id: int, user: dict = Depends(get_current_user)):
    """获取文件可读文本内容（用于前端预览渲染）。"""
    f = file_service.get_file(file_id)
    if not f:
        return {"ok": False, "code": "NOT_FOUND", "message": "文件不存在"}
    if f.get("owner_user_id") and f["owner_user_id"] != user["id"]:
        return {"ok": False, "code": "FORBIDDEN", "message": "无权访问"}
    path = f["path"]
    if not os.path.isfile(path):
        return {"ok": False, "code": "FILE_MISSING", "message": "文件已从磁盘移除"}
    try:
        from app.core.parser.router import router as parser_router
        text_mimes = {"text/plain", "text/markdown", "text/csv", "application/json", "text/html", "text/x-python", "text/typescript", "text/yaml", "text/xml"}
        mime = f["mime"] or ""
        if mime in text_mimes:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
        else:
            chunks = parser_router.parse(path)
            content = "\n\n".join(c.content for c in chunks) if chunks else "[无法提取文本内容]"
        return {"ok": True, "data": {"name": f["name"], "mime": mime, "content": content, "size": f["size"]}}
    except Exception as e:
        return {"ok": False, "code": "PARSE_ERROR", "message": str(e)}


@router.get("/{file_id}/chunks")
def get_chunks(file_id: int, limit: int = 50, offset: int = 0, user: dict = Depends(get_current_user)):
    from app.db.database import query
    f = file_service.get_file(file_id)
    if f and f.get("owner_user_id") and f["owner_user_id"] != user["id"]:
        return {"ok": False, "code": "FORBIDDEN", "message": "无权访问"}
    rows = query(
        "SELECT * FROM file_chunks WHERE file_id = ? ORDER BY chunk_index LIMIT ? OFFSET ?",
        (file_id, limit, offset),
    )
    return {"ok": True, "data": [dict(r) for r in rows]}


# ── 向量统计 ──────────────────────────────
@router.get("/vector/count")
def vector_count():
    return {"ok": True, "data": {"count": store.count()}}