"""PyMuPDF 流式 PDF 解析器。"""
from __future__ import annotations
import fitz  # PyMuPDF
from .base import BaseParser, Chunk
from typing import Iterator


class PDFParser(BaseParser):
    extensions = [".pdf"]

    def parse(self, path: str, progress_cb=None) -> Iterator[Chunk]:
        doc = fitz.open(path)
        total = len(doc)
        offset = 0
        for i, page in enumerate(doc):
            text = page.get_text()
            if not text.strip():
                continue
            yield Chunk(
                content=text,
                char_start=offset,
                char_end=offset + len(text),
                metadata={"page": i + 1, "total_pages": total},
            )
            offset += len(text)
            if progress_cb:
                progress_cb(int((i + 1) / total * 100))
        doc.close()