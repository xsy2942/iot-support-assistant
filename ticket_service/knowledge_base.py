from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KNOWLEDGE_PATH = ROOT / "data" / "processed" / "knowledge_chunks.csv"


@dataclass(frozen=True)
class KnowledgeHit:
    chunk_id: str
    source_type: str
    title: str
    product_line: str
    device_model: str
    error_code: str
    issue_type: str
    content: str
    score: float


class KnowledgeBase:
    """Local hybrid retrieval over the project's generated IoT support chunks."""

    def __init__(self, path: Path = DEFAULT_KNOWLEDGE_PATH) -> None:
        self.path = path
        self.rows = self._read_rows(path)
        self.corpus = [self._row_text(row) for row in self.rows]
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
        self.matrix = self.vectorizer.fit_transform(self.corpus) if self.corpus else None

    def search(self, query: str, top_k: int = 3) -> list[KnowledgeHit]:
        if not self.rows or self.matrix is None:
            return []
        vector_scores = cosine_similarity(self.vectorizer.transform([query]), self.matrix).ravel()
        keyword_scores = [self._keyword_score(query, row) for row in self.rows]
        combined_scores = [
            round(float(vector_scores[index]) * 0.72 + keyword_scores[index] * 0.28, 4)
            for index in range(len(self.rows))
        ]
        top_indices = sorted(range(len(self.rows)), key=lambda index: combined_scores[index], reverse=True)[:top_k]
        return [self._to_hit(self.rows[index], combined_scores[index]) for index in top_indices if combined_scores[index] > 0]

    @staticmethod
    def _read_rows(path: Path) -> list[dict[str, str]]:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            return list(csv.DictReader(file))

    @staticmethod
    def _row_text(row: dict[str, str]) -> str:
        return " ".join(
            [
                row.get("title", ""),
                row.get("device_model", ""),
                row.get("error_code", ""),
                row.get("issue_type", ""),
                row.get("content", ""),
            ]
        )

    @staticmethod
    def _keyword_score(query: str, row: dict[str, str]) -> float:
        text = KnowledgeBase._row_text(row).lower()
        terms = [term.lower() for term in re.findall(r"[A-Za-z]+-\d+|E\d{3}|MQTT|[A-Za-z0-9_.-]+|[\u4e00-\u9fff]{2,}", query)]
        if not terms:
            return 0.0
        matched = sum(1 for term in terms if term in text)
        exact_boost = 0.0
        if row.get("error_code") and row["error_code"].lower() in query.lower():
            exact_boost += 0.25
        if row.get("device_model") and row["device_model"].lower() in query.lower():
            exact_boost += 0.18
        return min(1.0, matched / len(terms) + exact_boost)

    @staticmethod
    def _to_hit(row: dict[str, str], score: float) -> KnowledgeHit:
        return KnowledgeHit(
            chunk_id=row.get("chunk_id", ""),
            source_type=row.get("source_type", ""),
            title=row.get("title", ""),
            product_line=row.get("product_line", ""),
            device_model=row.get("device_model", ""),
            error_code=row.get("error_code", ""),
            issue_type=row.get("issue_type", ""),
            content=row.get("content", ""),
            score=score,
        )
