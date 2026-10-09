from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class QARecord:
    qa_id: str
    domain: str
    q_type: str
    question: str
    answer: str
    source: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_text(self) -> str:
        return "\n".join(
            [
                f"domain: {self.domain}",
                f"q_type: {self.q_type}",
                f"question: {self.question}",
                f"answer: {self.answer}",
            ]
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, row: dict[str, Any], fallback_id: str = "") -> "QARecord | None":
        question = first_value(row, ["question", "Question", "q", "Q", "query", "utterance"])
        answer = first_value(row, ["answer", "Answer", "a", "A", "response", "completion"])
        if not question or not answer:
            return None

        qa_id = first_value(row, ["qa_id", "id", "uid", "qid"]) or fallback_id
        domain = first_value(row, ["domain", "department", "category", "subject"]) or "unknown"
        q_type = first_value(row, ["q_type", "question_type", "type"]) or "unknown"
        source = first_value(row, ["source", "dataset"]) or "aihub_or_sample"

        known = {"qa_id", "id", "uid", "qid", "domain", "department", "category", "subject", "q_type", "question_type", "type", "question", "Question", "q", "Q", "query", "utterance", "answer", "Answer", "a", "A", "response", "completion", "source", "dataset"}
        metadata = {k: v for k, v in row.items() if k not in known}

        return cls(
            qa_id=str(qa_id),
            domain=str(domain),
            q_type=str(q_type),
            question=str(question).strip(),
            answer=str(answer).strip(),
            source=str(source),
            metadata=metadata,
        )


def first_value(row: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None
