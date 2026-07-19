"""python-docx 流式解析器。"""
from __future__ import annotations
from docx import Document
from .base import BaseParser, Chunk
from typing import Iterator


class DocxParser(BaseParser):
    extensions = [".docx", ".doc"]

    def parse(self, path: str, progress_cb=None) -> Iterator[Chunk]:
        doc = Document(path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        total = len(paragraphs)
        offset = 0
        for i, para in enumerate(paragraphs):
            yield Chunk(
                content=para,
                char_start=offset,
                char_end=offset + len(para),
                metadata={"paragraph": i + 1, "total_paragraphs": total},
            )
            offset += len(para)
            if progress_cb and total > 0:
                progress_cb(int((i + 1) / total * 100))