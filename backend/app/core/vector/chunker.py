"""滑动窗口分块器。"""
from __future__ import annotations
from typing import Iterator


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[dict]:
    """滑动窗口分块,返回 [{text, index, char_start, char_end}]。"""
    if not text:
        return []
    chunks = []
    start = 0
    idx = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk_text = text[start:end]
        chunks.append({
            "text": chunk_text,
            "index": idx,
            "char_start": start,
            "char_end": end,
        })
        idx += 1
        if end >= len(text):
            break
        start = end - overlap
    return chunks