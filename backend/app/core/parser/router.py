"""
ParserRouter — 按 MIME / 扩展名自动分发到对应解析器。
"""
from __future__ import annotations
from pathlib import Path
from typing import Iterator, Callable
from .base import BaseParser, Chunk
from .pdf_parser import PDFParser
from .docx_parser import DocxParser
from .excel_parser import ExcelParser
from .text_parser import TextParser
from .ocr_parser import OcrParser


class ParserRouter:
    """多格式分发器。"""

    def __init__(self):
        self._parsers: list[BaseParser] = [
            PDFParser(),
            DocxParser(),
            ExcelParser(),
            TextParser(),
            OcrParser(),
        ]

    def register(self, parser: BaseParser):
        self._parsers.append(parser)

    def get_parser(self, path: str) -> BaseParser | None:
        for p in self._parsers:
            if p.validate(path):
                return p
        return None

    def parse(self, path: str, progress_cb: Callable[[int], None] | None = None) -> list[Chunk]:
        """解析文件,返回所有 Chunk。"""
        parser = self.get_parser(path)
        if not parser:
            raise ValueError(f"不支持的文件格式: {path}")
        return list(parser.parse(path, progress_cb))


router = ParserRouter()