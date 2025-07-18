# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol, runtime_checkable

@runtime_checkable
class OCREngine(Protocol):
    def extract_text(self, data: bytes, filename: str) -> str: ...

class BaseEngine(ABC):

    @abstractmethod
    def extract_text(self, data: bytes, filename: str) -> str: ...

    # small helper
    @staticmethod
    def _ext(path: str | Path) -> str:
        return Path(path).suffix.lower()

