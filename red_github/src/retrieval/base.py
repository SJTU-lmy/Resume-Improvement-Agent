# -*- coding: utf-8 -*-
"""检索统一接口。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class RetrievalResult:
    text: str
    score: float
    source: str


class BaseRetriever:
    name = "base"

    def index(self, docs: List[Dict]) -> None:
        """docs: [{"path": str, "text": str}, ...]"""
        raise NotImplementedError

    def search(self, query: str, top_k: int = 3) -> List[RetrievalResult]:
        raise NotImplementedError

    def search_texts(self, query: str, top_k: int = 3) -> List[str]:
        return [r.text for r in self.search(query, top_k)]
