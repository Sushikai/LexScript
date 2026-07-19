"""
BaseParser — 所有解析器的统一接口。
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class Chunk:
    content: str
    char_start: int = 0
    char_end: int = 0
    metadata: dict = field(default_factory=dict)  # page/row/sheet 等


class BaseParser(ABC):
    """所有文件解析器的基类。"""

    extensions: list[str] = []

    @abstractmethod
    def parse(self, path: str, progress_cb=None) -> Iterator[Chunk]:
        """解析文件,流式 yield Chunk。"""
        ...

    def validate(self, path: str) -> bool:
        """校验文件是否可解析。"""
        return any(path.lower().endswith(ext) for ext in self.extensions)