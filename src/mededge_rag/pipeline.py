from __future__ import annotations

from .generation import answer_question
from .vector_store import HashingVectorIndex


def ask(index_path: str, question: str, top_k: int = 3, use_llm: bool = True) -> tuple[str, list[dict[str, str | float]]]:
    index = HashingVectorIndex.load(index_path)
    hits = index.search(question, top_k=top_k)
    answer = answer_question(question, hits, use_llm=use_llm)
    evidence = [
        {
            "qa_id": hit.record.qa_id,
            "domain": hit.record.domain,
            "q_type": hit.record.q_type,
            "score": round(hit.score, 4),
        }
        for hit in hits
    ]
    return answer, evidence
