from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .schema import QARecord

TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[가-힣]+")
STOPWORDS = {
    "어떻게",
    "해야",
    "하나요",
    "하나",
    "무엇인가요",
    "무엇",
    "있으면",
    "나면",
    "때",
    "중",
}


@dataclass(slots=True)
class SearchHit:
    record: QARecord
    score: float


class HashingVectorIndex:
    def __init__(self, dims: int = 4096) -> None:
        self.dims = dims
        self.records: list[QARecord] = []
        self.vectors: list[dict[int, float]] = []

    def add(self, records: list[QARecord]) -> None:
        for record in records:
            self.records.append(record)
            self.vectors.append(vectorize(index_text(record), self.dims))

    def search(self, query: str, top_k: int = 3) -> list[SearchHit]:
        query_vec = vectorize(query, self.dims)
        scored: list[SearchHit] = []
        for record, vector in zip(self.records, self.vectors, strict=True):
            score = dot(query_vec, vector)
            if score > 0:
                scored.append(SearchHit(record=record, score=score))
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return scored[:top_k]

    def save(self, path: str | Path) -> None:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "dims": self.dims,
            "records": [record.to_dict() for record in self.records],
            "vectors": [{str(k): v for k, v in vector.items()} for vector in self.vectors],
        }
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "HashingVectorIndex":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        index = cls(dims=int(payload["dims"]))
        index.records = [QARecord.from_dict(row, fallback_id=f"loaded-{idx}") for idx, row in enumerate(payload["records"], start=1)]
        index.records = [record for record in index.records if record is not None]
        index.vectors = [{int(k): float(v) for k, v in vector.items()} for vector in payload["vectors"]]
        return index


def vectorize(text: str, dims: int) -> dict[int, float]:
    features: Counter[str] = Counter()
    for token in TOKEN_RE.findall(text.lower()):
        variants = {token}
        if re.fullmatch(r"[가-힣]+", token):
            variants.add(strip_korean_suffix(token))
        for variant in variants:
            if variant and variant not in STOPWORDS:
                features[variant] += 2.0
        if re.fullmatch(r"[가-힣]+", token) and len(token) >= 3:
            normalized = strip_korean_suffix(token)
            if normalized in STOPWORDS:
                continue
            for n in (2, 3):
                for i in range(max(0, len(normalized) - n + 1)):
                    features[normalized[i : i + n]] += 0.25

    hashed: dict[int, float] = {}
    for feature, weight in features.items():
        bucket = stable_hash(feature) % dims
        hashed[bucket] = hashed.get(bucket, 0.0) + weight

    norm = math.sqrt(sum(value * value for value in hashed.values()))
    if norm == 0:
        return {}
    return {key: value / norm for key, value in hashed.items()}


def index_text(record: QARecord) -> str:
    return "\n".join(
        [
            record.question,
            record.question,
            record.domain,
            record.q_type,
            record.answer,
            record.answer,
        ]
    )


def strip_korean_suffix(token: str) -> str:
    suffixes = ("으로", "에서", "에게", "하고", "하면", "해야", "나요", "인가요", "은", "는", "이", "가", "을", "를", "과", "와", "도", "에", "의", "로", "고")
    for suffix in suffixes:
        if token.endswith(suffix) and len(token) > len(suffix) + 1:
            return token[: -len(suffix)]
    return token


def stable_hash(value: str) -> int:
    return int(hashlib.sha1(value.encode("utf-8")).hexdigest()[:16], 16)


def dot(left: dict[int, float], right: dict[int, float]) -> float:
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(key, 0.0) for key, value in left.items())
