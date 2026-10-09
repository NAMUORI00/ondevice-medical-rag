from pathlib import Path
import json
import zipfile

from mededge_rag.generation import DISCLAIMER, answer_question
from mededge_rag.ingest import load_records
from mededge_rag.pipeline import ask
from mededge_rag.schema import QARecord
from mededge_rag.vector_store import HashingVectorIndex
from mededge_rag.vector_store import SearchHit


def sample_records() -> list[QARecord]:
    return [
        QARecord(
            qa_id="sample-001",
            domain="소아청소년과",
            q_type="응급상황",
            question="아이가 고열이고 경련하면 응급실에 가야 하나요?",
            answer="고열과 경련이 동반되면 응급의료기관 방문이 필요합니다.",
        )
    ]


def test_sample_retrieval(tmp_path: Path) -> None:
    index = HashingVectorIndex()
    index.add(sample_records())
    hits = index.search("아이가 고열이고 경련하면 응급실에 가야 하나요?", top_k=3)
    assert hits
    assert hits[0].record.qa_id == "sample-001"


def test_aihub_zip_loading(tmp_path: Path) -> None:
    zip_path = tmp_path / "Sample.zip"
    payload = {
        "qa_id": 9001,
        "domain": 17,
        "q_type": 1,
        "question": "테스트용 합성 질문입니다. 보기 중 올바른 것은 무엇인가?",
        "answer": "2) 테스트용 합성 정답",
    }
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("Sample/02.라벨링데이터/내과/필수_9001.json", json.dumps(payload, ensure_ascii=False))

    records = load_records(zip_path)

    assert len(records) == 1
    assert records[0].qa_id == "9001"
    assert records[0].domain == "내과"
    assert records[0].q_type == "객관식"


def test_ask_returns_answer_evidence_and_safety_notice(tmp_path: Path) -> None:
    index_path = tmp_path / "index.json"
    index = HashingVectorIndex()
    index.add(sample_records())
    index.save(index_path)

    answer, evidence = ask(str(index_path), "아이가 고열이고 경련하면 응급실에 가야 하나요?", use_llm=False)

    assert evidence
    assert evidence[0]["qa_id"] == "sample-001"
    assert evidence[0]["domain"] == "소아청소년과"
    assert "근거: sample-001" in answer
    assert DISCLAIMER in answer


def test_llm_answer_is_used_when_local_client_is_available(monkeypatch) -> None:
    calls = []

    class FakeClient:
        def available(self) -> bool:
            return True

        def chat(self, system: str, prompt: str) -> str:
            calls.append((system, prompt))
            return "근거 기반 답변입니다. 참조: sample-001, 소아청소년과"

    record = QARecord(
        qa_id="sample-001",
        domain="소아청소년과",
        q_type="응급상황",
        question="아이가 고열일 때 언제 응급실에 가야 하나요?",
        answer="경련이 동반되면 응급의료기관에 방문해야 합니다.",
    )
    hits = [SearchHit(record=record, score=0.9)]
    monkeypatch.setattr("mededge_rag.generation.OllamaClient", FakeClient)

    answer = answer_question("아이가 고열이면?", hits, use_llm=True)

    assert calls
    assert "qa_id=sample-001" in calls[0][1]
    assert "domain=소아청소년과" in calls[0][1]
    assert "근거 기반 답변입니다." in answer
    assert DISCLAIMER in answer
