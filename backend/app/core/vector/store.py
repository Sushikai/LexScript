"""ChromaDB 向量存储封装。"""
from __future__ import annotations
import time
from typing import Any
import chromadb
from chromadb.config import Settings
from loguru import logger
from app.config import VECTOR_STORE_PATH


class VectorStore:
    """Chroma 持久化客户端封装。"""

    def __init__(self, path: str | None = None):
        self._path = path or str(VECTOR_STORE_PATH)
        self._client = chromadb.PersistentClient(
            path=self._path,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, ids: list[str], embeddings: list[list[float]],
            documents: list[str], metadatas: list[dict] | None = None):
        """增量添加向量。"""
        if not ids:
            return
        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas or [{}] * len(ids),
        )

    def search(self, query_embedding: list[float], top_k: int = 20,
               where: dict | None = None) -> list[dict[str, Any]]:
        """向量检索。"""
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
        )
        if not results["ids"]:
            return []
        output = []
        for i in range(len(results["ids"][0])):
            output.append({
                "id": results["ids"][0][i],
                "score": results["distances"][0][i] if results["distances"] else 0,
                "document": results["documents"][0][i] if results["documents"] else "",
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
            })
        return output

    def delete_by_metadata(self, key: str, value: Any):
        """按 metadata 字段删除(如 file_id)。"""
        try:
            self._collection.delete(where={key: value})
        except Exception as e:
            logger.warning(f"[vector] delete error: {e}")

    def count(self) -> int:
        return self._collection.count()

    def delete_all(self):
        self._client.delete_collection("documents")
        self._collection = self._client.get_or_create_collection(name="documents")


store = VectorStore()