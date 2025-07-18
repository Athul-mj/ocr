from __future__ import annotations
import logging

from ..engines.tesseract_engine import TesseractEngine
from ..parsers.invoice_parser import InvoiceParser, ParseError

log = logging.getLogger(__name__)

_engine = TesseractEngine()
_parser = InvoiceParser(min_score=0.6) 

def process_invoice(file_obj) -> dict:
    """
    High-level façade combining OCR and parser.
    Raises `ParseError` if parsing fails or score too low.
    """
    data = file_obj.read()
    text = _engine.extract_text(data, file_obj.name)
    result = _parser.parse(text)
    log.info("Invoice parsed (score %.2f): %s", result.score, result.invoice_number)
    return result.dict()
