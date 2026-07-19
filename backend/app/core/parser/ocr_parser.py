"""
OCR Image Parser — 用 pytesseract 识别图片文字。
当 pytesseract / PIL 不可用时静默降级（记录日志）。
"""
from __future__ import annotations
from typing import Iterator, Callable
from loguru import logger
from .base import BaseParser, Chunk

try:
    from PIL import Image
    import pytesseract
    HAS_OCR = True
except ImportError as e:
    HAS_OCR = False
    logger.warning(f"[OCR] pytesseract/PIL 不可用, OCR 解析已禁用: {e}")


class OcrParser(BaseParser):
    """图片 OCR 解析器,支持常见图片格式。"""

    extensions = [".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff"]

    @staticmethod
    def available() -> bool:
        """检测 OCR 是否可用（依赖已安装）。"""
        return HAS_OCR

    def parse(self, path: str, progress_cb: Callable[[int], None] | None = None) -> Iterator[Chunk]:
        if not HAS_OCR:
            logger.warning(f"[OCR] 跳过 {path}: pytesseract/PIL 未安装")
            if progress_cb:
                progress_cb(100)
            return
        try:
            img = Image.open(path)
            text = pytesseract.image_to_string(img, lang="chi_sim+eng")
            if progress_cb:
                progress_cb(100)
            if text.strip():
                yield Chunk(
                    content=text.strip(),
                    char_start=0,
                    char_end=len(text),
                    metadata={"source": path, "format": "ocr", "lang": "chi_sim+eng"},
                )
        except Exception as e:
            logger.error(f"[OCR] 解析失败 {path}: {e}")
            if progress_cb:
                progress_cb(100)
