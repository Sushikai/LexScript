"""File service — 文件 CRUD + 导入/解析/索引管道。"""
from __future__ import annotations
import os
import time
import json
import hashlib
from pathlib import Path
from typing import Callable
from app.db.database import query, query_one, execute
from app.core.parser.router import router as parser_router
from app.core.parser.base import Chunk
from app.core.vector.chunker import chunk_text
from app.config import CHUNK_SIZE, CHUNK_OVERLAP


MIME_MAP = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".json": "application/json",
}


def _now() -> int:
    return int(time.time())


# ── 文件夹 CRUD ─────────────────────────────
def create_folder(name: str, root_path: str, case_number: str | None = None,
                  description: str | None = None, owner_user_id: int = 0) -> dict:
    now = _now()
    execute(
        "INSERT INTO case_folders (name, root_path, case_number, description, owner_user_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, root_path, case_number, description, owner_user_id, now, now),
    )
    row = query_one("SELECT * FROM case_folders WHERE id = last_insert_rowid()")
    return dict(row) if row else {}


def list_folders(user_id: int = 0) -> list[dict]:
    """列出文件夹。普通用户只看自己的;admin 通过 user_id=0 可看全部。"""
    if user_id == 0:
        rows = query("SELECT * FROM case_folders ORDER BY updated_at DESC")
    else:
        rows = query("SELECT * FROM case_folders WHERE owner_user_id = ? ORDER BY updated_at DESC", (user_id,))
    return [dict(r) for r in rows]


# ── 文件 CRUD ───────────────────────────────
def import_file(path: str, folder_id: int | None = None, owner_user_id: int = 0) -> dict:
    """导入单文件(递归扫描目录时逐文件调用)。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    sha256 = hashlib.sha256(p.read_bytes()).hexdigest()
    mime = MIME_MAP.get(p.suffix.lower(), "application/octet-stream")
    now = _now()
    abs_path = str(p.resolve())

    # 检查重复(只查同用户)
    existing = query_one("SELECT id FROM files WHERE sha256 = ? AND owner_user_id = ?", (sha256, owner_user_id))
    if existing:
        return dict(query_one("SELECT * FROM files WHERE id = ?", (existing["id"],)))

    execute(
        """INSERT INTO files (folder_id, path, name, size, mime, sha256, status, owner_user_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)""",
        (folder_id, abs_path, p.name, p.stat().st_size, mime, sha256, owner_user_id, now, now),
    )
    return dict(query_one("SELECT * FROM files WHERE id = last_insert_rowid()"))


def scan_directory(dir_path: str, folder_id: int | None = None, owner_user_id: int = 0) -> list[dict]:
    """递归扫描目录,导入所有支持的文件。"""
    supported_exts = tuple(MIME_MAP.keys())
    base = Path(dir_path)
    results = []
    for f in base.rglob("*"):
        if f.is_file() and f.suffix.lower() in supported_exts:
            try:
                results.append(import_file(str(f), folder_id, owner_user_id))
            except Exception:
                pass
    return results


def list_files(folder_id: int | None = None, status: str | None = None,
               limit: int = 100, offset: int = 0,
               user_id: int = 0) -> list[dict]:
    """列出文件。user_id=0 看全部,否则只看自己的。"""
    conditions = []
    params = []
    if user_id:
        conditions.append("owner_user_id = ?")
        params.append(user_id)
    if folder_id is not None:
        conditions.append("folder_id = ?")
        params.append(folder_id)
    if status:
        conditions.append("status = ?")
        params.append(status)
    where = " AND ".join(conditions) if conditions else "1"
    rows = query(
        f"SELECT * FROM files WHERE {where} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
        tuple(params + [limit, offset]),
    )
    return [dict(r) for r in rows]


def get_file(file_id: int) -> dict | None:
    row = query_one("SELECT * FROM files WHERE id = ?", (file_id,))
    return dict(row) if row else None


def delete_file(file_id: int):
    file = get_file(file_id)
    if file:
        # 删除分片
        execute("DELETE FROM file_chunks WHERE file_id = ?", (file_id,))
        # 删除向量(通过 vector_service)
        from app.core.vector.store import store
        store.delete_by_metadata("file_id", str(file_id))
        # 删除文件记录
        execute("DELETE FROM files WHERE id = ?", (file_id,))


# ── 解析 + 索引 ─────────────────────────────
def parse_file(file_id: int, progress_cb: Callable | None = None) -> list[Chunk]:
    """解析文件 → file_chunks 表。"""
    file = get_file(file_id)
    if not file:
        raise ValueError(f"文件不存在: {file_id}")

    execute("UPDATE files SET status = 'parsing', updated_at = ? WHERE id = ?", (_now(), file_id))
    try:
        raw_chunks = parser_router.parse(file["path"], progress_cb)
        # 对超大 chunk 进行二次分割 (chunk_text 控制分块大小)
        final_chunks = []
        for c in raw_chunks:
            if len(c.content) > CHUNK_SIZE:
                sub = chunk_text(c.content, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
                for s in sub:
                    final_chunks.append(Chunk(
                        content=s["text"],
                        char_start=c.char_start + s["char_start"],
                        char_end=c.char_start + s["char_end"],
                        metadata=c.metadata,
                    ))
            else:
                final_chunks.append(c)
        # 写 file_chunks
        for idx, c in enumerate(final_chunks):
            execute(
                "INSERT INTO file_chunks (file_id, chunk_index, content, char_start, char_end, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                (file_id, idx, c.content, c.char_start, c.char_end,
                 json.dumps(c.metadata, ensure_ascii=False)),
            )
        execute(
            "UPDATE files SET status = 'indexed', chunk_count = ?, updated_at = ? WHERE id = ?",
            (len(final_chunks), _now(), file_id),
        )
        return final_chunks
    except Exception as e:
        execute("UPDATE files SET status = 'failed', error = ?, updated_at = ? WHERE id = ?",
                (str(e), _now(), file_id))
        raise


def index_chunks_to_vector(file_id: int, api_key: str = ""):
    """将 file_chunks 向量化 → ChromaDB。"""
    file = get_file(file_id)
    if not file:
        return
    chunks = query("SELECT * FROM file_chunks WHERE file_id = ? ORDER BY chunk_index", (file_id,))
    if not chunks:
        return

    from app.core.vector.embedder import Embedder
    from app.core.vector.store import store
    embedder = Embedder(api_key=api_key)
    texts = [r["content"] for r in chunks]
    embeddings = embedder.embed(texts)

    ids = [f"file_{file_id}_chunk_{r['chunk_index']}" for r in chunks]
    metadatas = [{"file_id": str(file_id), "file_name": file["name"], "chunk_index": r["chunk_index"]}
                 for r in chunks]
    store.add(ids, embeddings, texts, metadatas)
    embedder.close()