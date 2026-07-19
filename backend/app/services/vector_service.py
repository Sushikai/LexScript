"""Vector service — 检索编排。"""
from __future__ import annotations
from app.core.vector.store import store
from app.core.vector.embedder import Embedder
from app.core.vector.hybrid import hybrid
from app.core.vector.chunker import chunk_text
from app.config import TOP_K, HYBRID_VECTOR_WEIGHT


def search_semantic(query: str, api_key: str = "", top_k: int = TOP_K,
                    where: dict | None = None) -> list[dict]:
    """纯向量检索。"""
    embedder = Embedder(api_key=api_key)
    q_emb = embedder.embed([query])
    embedder.close()
    if not q_emb or not q_emb[0]:
        return []
    results = store.search(q_emb[0], top_k=top_k, where=where)
    return results


def search_hybrid(query: str, api_key: str = "", top_k: int = TOP_K,
                  where: dict | None = None) -> list[dict]:
    """混合检索:向量 + BM25。"""
    embedder = Embedder(api_key=api_key)
    q_emb = embedder.embed([query])
    embedder.close()
    if not q_emb or not q_emb[0]:
        return []
    vec_results = store.search(q_emb[0], top_k=top_k * 2, where=where)
    docs = [r["document"] for r in vec_results]
    return hybrid.hybrid_search(query, vec_results, docs, top_k=top_k)


def search_by_keyword(query: str, top_k: int = TOP_K,
                      file_id: int | None = None) -> list[dict]:
    """关键词检索(SQLite LIKE)。"""
    from app.db.database import query as db_query
    conditions = ["content LIKE ?"]
    params = [f"%{query}%"]
    if file_id:
        conditions.append("file_id = ?")
        params.append(file_id)
    rows = db_query(
        f"SELECT id, file_id, chunk_index, content, metadata FROM file_chunks WHERE {' AND '.join(conditions)} LIMIT ?",
        tuple(params + [top_k]),
    )
    return [dict(r) for r in rows]