"""纯文本 / Markdown 解析器。"""
from __future__ import annotations
from pathlib import Path
from .base import BaseParser, Chunk
from typing import Iterator


class TextParser(BaseParser):
    extensions = [".txt", ".md", ".markdown", ".csv", ".json", ".xml", ".yaml", ".yml"]

    def parse(self, path: str, progress_cb=None) -> Iterator[Chunk]:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        yield Chunk(
            content=text,
            char_start=0,
            char_end=len(text),
            metadata={"filename": Path(path).name},
        )
        if progress_cb:
            progress_cb(100)