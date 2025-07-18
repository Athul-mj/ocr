# -*- coding: utf-8 -*-
from __future__ import annotations
import io, os, logging
from pathlib import Path
from typing import List
from decimal import Decimal
from .base import *
import pytesseract
from PIL import Image
from pdf2image import convert_from_bytes
from pdf2image.exceptions import (PDFInfoNotInstalledError, PDFPageCountError, PDFSyntaxError,)

logger = logging.getLogger(__name__)

class TesseractEngine(BaseEngine):
    def __init__(self, cmd: str | None = None, lang: str = "eng", poppler_path: str | None = None):
        pytesseract.pytesseract.tesseract_cmd = cmd or os.getenv("TESSERACT_CMD", "tesseract")
        self.lang = lang
        self.poppler_path = poppler_path or os.getenv("POPPLER_PATH")

    # ------------------------------------------------------------------
    def extract_text(self, data: bytes, filename: str) -> str:
        ext = self._ext(filename)
        if ext in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}:
            return self._img_to_text(Image.open(io.BytesIO(data)))

        if ext == ".pdf":
            pages = self._pdf_to_images(data)
            return "\n".join(self._img_to_text(p) for p in pages)

        raise ValueError(f"TesseractEngine does not support {ext}")

    # ------------------------------------------------------------------
    def _img_to_text(self, img: Image.Image) -> str:
        return pytesseract.image_to_string(img, lang=self.lang, config="--psm 6")

    # ------------------------------------------------------------------
    def _pdf_to_images(self, data: bytes) -> List[Image.Image]:
        try:
            return convert_from_bytes(
                data,
                dpi=300,
                fmt="png",
                poppler_path=self.poppler_path  
            )
        except PDFInfoNotInstalledError:
            logger.warning("Poppler not found ➜ falling back to PyMuPDF rasteriser")
            return self._pdf_via_pymupdf(data)

    # ------------------------------------------------------------------
    @staticmethod
    def _pdf_via_pymupdf(data: bytes) -> List[Image.Image]:
        import fitz 
        pages = []
        with fitz.open(stream=data, filetype="pdf") as doc:
            for page in doc:
                pix = page.get_pixmap(dpi=300)
                pages.append(Image.open(io.BytesIO(pix.tobytes())))
        return pages


