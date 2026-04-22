"""Lightweight RAG retriever over the local AutoStream knowledge base.

Uses BM25 (rank_bm25) for deterministic, dependency-light retrieval.
The KB is tiny, so BM25 is both fast and fully offline.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Dict

from rank_bm25 import BM25Okapi

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


class KnowledgeRetriever:
    """BM25 retriever over knowledge_base.json chunks."""

    def __init__(self, kb_path: str | Path = "knowledge_base.json"):
        kb_path = Path(kb_path)
        data = json.loads(kb_path.read_text(encoding="utf-8"))
        self.company: str = data.get("company", "")
        self.chunks: List[Dict] = data["chunks"]
        self._corpus_tokens = [_tokenize(c["text"]) for c in self.chunks]
        self._bm25 = BM25Okapi(self._corpus_tokens)

    def retrieve(self, query: str, k: int = 3) -> List[Dict]:
        if not query.strip():
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(
            zip(scores, self.chunks), key=lambda x: x[0], reverse=True
        )
        top = [c for score, c in ranked[:k] if score > 0]
        # Fallback: if nothing matched keywords, return top-k by raw rank.
        if not top:
            top = [c for _, c in ranked[:k]]
        return top

    def format_context(self, chunks: List[Dict]) -> str:
        if not chunks:
            return "(no relevant knowledge found)"
        return "\n\n".join(
            f"[{c['topic']}] {c['text']}" for c in chunks
        )
