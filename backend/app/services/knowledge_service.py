"""
Knowledge Base service — 知识库管理 / 文件监控 / 自动 REG（反向索引）。
所有文件操作通过此服务完成，默认路径 ~/LexScript/knowledge_base/。
"""
from __future__ import annotations
import os
import time
import json
import hashlib
import threading
import traceback
from pathlib import Path
from typing import Callable
from loguru import logger
from app.db.database import query, query_one, execute
from app.core.parser.router import router as parser_router
from app.core.vector.store import store
from app.core.vector.embedder import Embedder
from app.services.config_service import get_config, set_config

CONFIG_KEY_PATH = "knowledge_base_path"
DEFAULT_KB_PATH = str(Path.home() / "LexScript" / "knowledge_base")

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
    ".py": "text/x-python",
    ".ts": "text/typescript",
    ".vue": "text/html",
    ".js": "text/javascript",
    ".yaml": "text/yaml",
    ".yml": "text/yaml",
    ".html": "text/html",
    ".css": "text/css",
    ".xml": "text/xml",
}

KB_STATUS_PENDING = "pending"
KB_STATUS_INDEXING = "parsing"
KB_STATUS_INDEXED = "indexed"
KB_STATUS_FAILED = "failed"


def _now() -> int:
    return int(time.time())


# ── 路径 ─────────────────────────────────────

def get_kb_path() -> str:
    """获取当前 KB 路径，默认 ~/LexScript/knowledge_base/"""
    path = get_config(CONFIG_KEY_PATH)
    if path and os.path.isdir(path):
        return path
    os.makedirs(DEFAULT_KB_PATH, exist_ok=True)
    set_config(CONFIG_KEY_PATH, DEFAULT_KB_PATH)
    return DEFAULT_KB_PATH


def set_kb_path(path: str) -> str:
    """设置 KB 路径，自动创建目录。"""
    p = Path(path).resolve()
    p.mkdir(parents=True, exist_ok=True)
    set_config(CONFIG_KEY_PATH, str(p))
    return str(p)


# ── 文件扫描 ─────────────────────────────────

def scan_kb_files() -> list[dict]:
    """扫描 KB 目录，返回所有支持的文件列表。"""
    kb_path = get_kb_path()
    supported = tuple(MIME_MAP.keys())
    results = []
    for f in Path(kb_path).rglob("*"):
        if f.is_file() and f.suffix.lower() in supported:
            results.append({
                "path": str(f),
                "relative_path": str(f.relative_to(kb_path)),
                "name": f.name,
                "size": f.stat().st_size,
                "suffix": f.suffix.lower(),
                "mime": MIME_MAP.get(f.suffix.lower(), "application/octet-stream"),
            })
    return results


def get_kb_status() -> dict:
    """KB 概览：路径 / 文件数 / 各状态统计。"""
    kb_path = get_kb_path()
    registered = query("SELECT status, COUNT(*) as cnt FROM files GROUP BY status")
    stats = {r["status"]: r["cnt"] for r in registered}
    total_files = sum(1 for _ in Path(kb_path).rglob("*") if _.is_file())
    return {
        "path": kb_path,
        "total_on_disk": total_files,
        "registered": stats,
        "indexed": stats.get(KB_STATUS_INDEXED, 0),
        "pending": stats.get(KB_STATUS_PENDING, 0),
        "failed": stats.get(KB_STATUS_FAILED, 0),
    }


# ── 导入 + REG 管道 ─────────────────────────

def _compute_sha256(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def import_file(path: str) -> dict:
    """导入单个文件到 files 表（去重）。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    sha256 = _compute_sha256(str(p))
    existing = query_one("SELECT id FROM files WHERE sha256 = ?", (sha256,))
    if existing:
        return dict(query_one("SELECT * FROM files WHERE id = ?", (existing["id"],)))

    mime = MIME_MAP.get(p.suffix.lower(), "application/octet-stream")
    now = _now()
    execute(
        "INSERT INTO files (path, name, size, mime, sha256, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (str(p.resolve()), p.name, p.stat().st_size, mime, sha256, KB_STATUS_PENDING, now, now),
    )
    return dict(query_one("SELECT * FROM files WHERE id = last_insert_rowid()"))


def import_all_kb_files() -> list[dict]:
    """扫描 KB 目录，批量导入。"""
    results = []
    for f in scan_kb_files():
        try:
            results.append(import_file(f["path"]))
        except Exception as e:
            results.append({"path": f["path"], "error": str(e)})
    return results


# ── 全局 REG 锁（线程安全） ──────────────────

_reg_lock = threading.Lock()


def reg_file(file_id: int) -> dict:
    """
    对单个文件执行 REG（解析 → 分片 → 向量索引）。
    线程安全：同一时间只处理一个文件。幂等：多次调用安全。
    """
    with _reg_lock:
        return _reg_file_unsafe(file_id)


def _reg_file_unsafe(file_id: int) -> dict:
    file_row = query_one("SELECT * FROM files WHERE id = ?", (file_id,))
    if not file_row:
        raise ValueError(f"文件不存在: {file_id}")

    # 已索引或正在索引的不再重复执行
    if file_row["status"] in (KB_STATUS_INDEXED, KB_STATUS_INDEXING):
        return {"file_id": file_id, "status": file_row["status"], "chunks": file_row["chunk_count"]}

    # 标记为索引中
    _db_update(file_id, status=KB_STATUS_INDEXING, error=None)

    try:
        path = file_row["path"]

        # 1. 清理旧数据（幂等保证）
        execute("DELETE FROM file_chunks WHERE file_id = ?", (file_id,))
        try:
            store.delete_by_metadata("file_id", str(file_id))
        except Exception:
            pass  # ChromaDB 清理失败不阻断

        # 2. 解析
        chunks = parser_router.parse(path)

        # 3. 写 file_chunks
        for i, c in enumerate(chunks):
            execute(
                "INSERT INTO file_chunks (file_id, chunk_index, content, char_start, char_end, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                (file_id, i, c.content, c.char_start, c.char_end,
                 json.dumps(c.metadata, ensure_ascii=False)),
            )

        # 4. 向量化 → ChromaDB
        texts = [c.content for c in chunks]
        embedder = Embedder()
        try:
            embeddings = embedder.embed(texts)
            ids = [f"file_{file_id}_chunk_{i}" for i in range(len(chunks))]
            metadatas = [
                {"file_id": str(file_id), "file_name": file_row["name"], "chunk_index": i}
                for i in range(len(chunks))
            ]
            store.add(ids, embeddings, texts, metadatas)
        finally:
            embedder.close()

        # 5. 更新为已索引
        _db_update(file_id, status=KB_STATUS_INDEXED, chunk_count=len(chunks), error=None)
        return {"file_id": file_id, "status": KB_STATUS_INDEXED, "chunks": len(chunks)}

    except Exception as e:
        err_msg = f"{type(e).__name__}: {e}"
        logger.warning(f"[reg_file] 索引失败 file_id={file_id}: {err_msg}")
        _db_update(file_id, status=KB_STATUS_FAILED, error=err_msg)
        return {"file_id": file_id, "status": KB_STATUS_FAILED, "error": err_msg}


def _db_update(file_id: int, **kwargs):
    """安全更新 files 表字段（绕过 safe_write 避免递归异常）。"""
    sets = []
    params = []
    for k, v in kwargs.items():
        sets.append(f"{k} = ?")
        params.append(v)
    if not sets:
        return
    sets.append("updated_at = ?")
    params.append(_now())
    params.append(file_id)
    # 直接用原始连接执行（绕过 safe_write 的 retry 逻辑）
    from app.db.database import get_conn
    try:
        conn = get_conn()
        conn.execute(
            f"UPDATE files SET {', '.join(sets)} WHERE id = ?",
            params,
        )
    except Exception:
        # 终极兜底：静默失败
        pass


def reg_all_pending() -> list[dict]:
    """对所有 pending 文件执行 REG。"""
    rows = query("SELECT id FROM files WHERE status = ?", (KB_STATUS_PENDING,))
    results = []
    for r in rows:
        results.append(reg_file(r["id"]))
    return results


def recover_stale_indexing():
    """启动恢复：将卡在 parsing 状态的文件重置为 pending。"""
    rows = query("SELECT id, name, status FROM files WHERE status = ?", (KB_STATUS_INDEXING,))
    for r in rows:
        execute("UPDATE files SET status = ?, error = ?, updated_at = ? WHERE id = ?",
                (KB_STATUS_PENDING, f"recovered from {r['status']}", _now(), r["id"]))
        logger.info(f"[recover] 重置卡住文件 id={r['id']} name={r['name']}")

# ── 文件内容读取/写入 ───────────────────────

def read_file_content(file_id: int) -> dict:
    """读取文件原始内容（文本文件）。"""
    row = query_one("SELECT * FROM files WHERE id = ?", (file_id,))
    if not row:
        raise ValueError(f"文件不存在: {file_id}")
    path = row["path"]
    try:
        content = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = f"[二进制文件，无法直接读取] {path}"
    return {"id": file_id, "name": row["name"], "path": path, "content": content, "size": len(content)}


def write_file_content(file_id: int, content: str) -> dict:
    """写入文件内容。"""
    row = query_one("SELECT * FROM files WHERE id = ?", (file_id,))
    if not row:
        raise ValueError(f"文件不存在: {file_id}")
    Path(row["path"]).write_text(content, encoding="utf-8")
    new_sha = _compute_sha256(row["path"])
    execute("UPDATE files SET sha256 = ?, updated_at = ? WHERE id = ?",
            (new_sha, _now(), file_id))
    execute("UPDATE files SET status = ?, updated_at = ? WHERE id = ?",
            (KB_STATUS_PENDING, _now(), file_id))
    return {"id": file_id, "name": row["name"], "status": KB_STATUS_PENDING, "size": len(content)}


def create_file_in_kb(name: str, content: str = "") -> dict:
    """在 KB 目录创建新文件。"""
    kb_path = get_kb_path()
    file_path = Path(kb_path) / name
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return import_file(str(file_path))


# ── 文档向量索引（让 AI 可搜索到生成的法律文书） ──

def index_document_to_vector(doc_uuid: str, title: str, content: str) -> dict:
    """将生成的法律文书分块后索引到向量库，使 AI 可搜索到。"""
    from app.core.vector.chunker import chunk_text
    from app.core.vector.store import store as vec_store
    from app.core.vector.embedder import Embedder

    vec_store.delete_by_metadata("doc_uuid", doc_uuid)

    chunks = chunk_text(content, max_len=500, overlap=50)
    if not chunks:
        return {"doc_uuid": doc_uuid, "chunks": 0}

    embedder = Embedder()
    try:
        texts = [c.content for c in chunks]
        embeddings = embedder.embed(texts)
        ids = [f"doc_{doc_uuid}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {"doc_uuid": doc_uuid, "title": title, "chunk_index": i, "source": "document"}
            for i in range(len(chunks))
        ]
        vec_store.add(ids, embeddings, texts, metadatas)
        return {"doc_uuid": doc_uuid, "chunks": len(chunks), "title": title}
    finally:
        embedder.close()


def search_kb(query: str, top_k: int = 5) -> list[dict]:
    """知识库语义搜索 (Agent Tool 用)。"""
    return search_all(query, top_k=top_k)


def search_all(query: str, top_k: int = 10) -> list[dict]:
    """统一搜索：同时搜索知识库文件 + 法律文书。"""
    from app.core.vector.store import store as vec_store
    from app.core.vector.embedder import Embedder
    from app.core.vector.hybrid import hybrid as hybrid_search

    embedder = Embedder()
    try:
        q_emb = embedder.embed([query])
        if not q_emb or not q_emb[0]:
            return []
        results = vec_store.search(q_emb[0], top_k=top_k * 2)
        docs = [r["document"] for r in results]
        return hybrid_search.hybrid_search(query, results, docs, top_k=top_k)
    finally:
        embedder.close()


def search_documents(query: str, top_k: int = 5) -> list[dict]:
    """仅搜索法律文书。"""
    from app.core.vector.store import store as vec_store
    from app.core.vector.embedder import Embedder

    embedder = Embedder()
    try:
        q_emb = embedder.embed([query])
        if not q_emb or not q_emb[0]:
            return []
        return vec_store.search(q_emb[0], top_k=top_k, where={"source": "document"})
    finally:
        embedder.close()


def delete_document_from_vector(doc_uuid: str):
    """从向量库删除指定文档的索引。"""
    from app.core.vector.store import store as vec_store
    vec_store.delete_by_metadata("doc_uuid", doc_uuid)


def delete_file_from_kb(file_id: int):
    """删除文件记录及向量。"""
    row = query_one("SELECT id FROM files WHERE id = ?", (file_id,))
    if not row:
        return
    execute("DELETE FROM file_chunks WHERE file_id = ?", (file_id,))
    try:
        store.delete_by_metadata("file_id", str(file_id))
    except Exception:
        pass
    execute("DELETE FROM files WHERE id = ?", (file_id,))


# ── 知识库列表（含状态） ────────────────────

def list_kb_files(status: str | None = None) -> list[dict]:
    """列出 KB 中所有已注册文件。"""
    if status:
        rows = query("SELECT * FROM files WHERE status = ? ORDER BY updated_at DESC", (status,))
    else:
        rows = query("SELECT * FROM files ORDER BY updated_at DESC")
    return [dict(r) for r in rows]


def list_kb_on_disk() -> list[dict]:
    """列出 KB 目录实际文件（含是否已注册）。"""
    kb_path = get_kb_path()
    registered = {r["path"]: dict(r) for r in query("SELECT * FROM files")}
    results = []
    for f in scan_kb_files():
        reg = registered.get(f["path"])
        results.append({
            **f,
            "in_db": reg is not None,
            "file_id": reg["id"] if reg else None,
            "status": reg["status"] if reg else "unregistered",
            "chunks": reg.get("chunk_count", 0) if reg else 0,
        })
    return results


# ── 文件监控（简单轮询） ────────────────────

_watcher_running = False
_watcher_thread: threading.Thread | None = None
_watcher_seen: dict[str, float] = {}  # path → mtime
_watcher_seed_lock = threading.Lock()


def seed_watcher_seen():
    """预填充 watcher 的 seen 字典，避免启动时重复 REG。"""
    global _watcher_seen
    kb_path = get_kb_path()
    with _watcher_seed_lock:
        _watcher_seen.clear()
        for f in Path(kb_path).rglob("*"):
            if f.is_file() and f.suffix.lower() in MIME_MAP:
                _watcher_seen[str(f.resolve())] = f.stat().st_mtime


def _watch_loop(interval: int = 5):
    """后台轮询 KB 目录，自动导入新文件、检测修改与删除。"""
    global _watcher_running, _watcher_seen
    seen = _watcher_seen
    while _watcher_running:
        try:
            kb_path = get_kb_path()
            current_paths: dict[str, float] = {}
            for f in Path(kb_path).rglob("*"):
                if f.is_file() and f.suffix.lower() in MIME_MAP:
                    fp = str(f.resolve())
                    mtime = f.stat().st_mtime
                    current_paths[fp] = mtime
                    if fp not in seen:
                        seen[fp] = mtime
                        try:
                            fdata = import_file(fp)
                            if fdata and fdata.get("id") and fdata.get("status") == KB_STATUS_PENDING:
                                threading.Thread(target=reg_file, args=(fdata["id"],), daemon=True).start()
                        except Exception:
                            pass
                    elif seen.get(fp) != mtime:
                        seen[fp] = mtime
                        try:
                            f_row = query_one("SELECT id FROM files WHERE path = ?", (fp,))
                            if f_row:
                                execute("DELETE FROM file_chunks WHERE file_id = ?", (f_row["id"],))
                                try:
                                    store.delete_by_metadata("file_id", str(f_row["id"]))
                                except Exception:
                                    pass
                                execute("DELETE FROM files WHERE id = ?", (f_row["id"],))
                            fdata = import_file(fp)
                            if fdata and fdata.get("id"):
                                reg_file(fdata["id"])
                        except Exception:
                            pass

            for fp in list(seen.keys()):
                if fp not in current_paths:
                    seen.pop(fp, None)
                    try:
                        f_row = query_one("SELECT id FROM files WHERE path = ?", (fp,))
                        if f_row:
                            execute("DELETE FROM file_chunks WHERE file_id = ?", (f_row["id"],))
                            try:
                                store.delete_by_metadata("file_id", str(f_row["id"]))
                            except Exception:
                                pass
                            execute("DELETE FROM files WHERE id = ?", (f_row["id"],))
                    except Exception:
                        pass
        except Exception:
            pass
        time.sleep(interval)


def start_watcher(interval: int = 5):
    """启动文件监控（非阻塞）。"""
    global _watcher_running, _watcher_thread
    if _watcher_running:
        return
    _watcher_running = True
    _watcher_thread = threading.Thread(target=_watch_loop, args=(interval,), daemon=True)
    _watcher_thread.start()


def stop_watcher():
    global _watcher_running
    _watcher_running = False
