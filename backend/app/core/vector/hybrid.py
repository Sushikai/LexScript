"""BM25 + 向量混合检索。"""
from __future__ import annotations
from typing import Any


class HybridSearch:
    """混合检索:向量召回 + BM25 关键词召回,加权融合。"""

    def __init__(self, vector_weight: float = 0.7):
        self.vector_weight = vector_weight

    def _bm25_score(self, query: str, document: str) -> float:
        """简化 BM25:支持中英文关键词匹配。"""
        if not query or not document:
            return 0.0
        q_lower = query.lower()
        d_lower = document.lower()

        # 判断是否含中文:含中文则走字符匹配，否则走英文分词
        has_cjk = any('一' <= c <= '鿿' for c in query)

        if has_cjk:
            # 中文模式:子串匹配 + 字符命中
            d = d_lower
            match_count = d.count(q_lower)
            if match_count > 0:
                return min(1.0, match_count / 3.0)  # 3次命中=满分
            # 字符级别:每个汉字单独匹配
            chars = [c for c in q_lower if '一' <= c <= '鿿']
            if not chars:
                return 0.0
            hits = sum(1 for c in chars if c in d)
            return hits / len(chars) * 0.5  # 字符匹配最多0.5分
        else:
            # 英文模式:空格分词匹配
            q_words = q_lower.split()
            if not q_words:
                return 0.0
            d_words_set = set(d_lower.split())
            hits = sum(1 for w in q_words if w in d_words_set)
            return hits / len(q_words)

    def hybrid_search(self, query: str, vector_results: list[dict],
                      documents: list[str], top_k: int = 20) -> list[dict]:
        """融合向量 + BM25 结果。"""
        max_v = max((r["score"] for r in vector_results), default=1.0)
        # 全零向量:直接退化为 BM25 排序
        all_zero = max_v == 1.0 and all(r["score"] == 1.0 for r in vector_results)

        bm25_scores = [self._bm25_score(query, doc) for doc in documents]
        fused = []
        for vr in vector_results:
            if all_zero:
                v_score = 0.0
            else:
                v_score = 1.0 - vr["score"] / max_v if max_v > 0 else 0.5
            doc_idx = vector_results.index(vr)
            bm25 = bm25_scores[doc_idx] if doc_idx < len(bm25_scores) else 0
            fused_score = self.vector_weight * v_score + (1 - self.vector_weight) * bm25
            # 全零时只用 BM25
            if all_zero:
                fused_score = bm25
            fused.append({
                **vr,
                "vector_score": v_score,
                "bm25_score": bm25,
                "final_score": fused_score,
            })

        fused.sort(key=lambda x: x["final_score"], reverse=True)
        return fused[:top_k]


hybrid = HybridSearch()