from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from mededge_rag.evaluation import (
    DEFAULT_GENERATION_MODEL,
    DEFAULT_JUDGE_MODEL,
    DEFAULT_JUDGE_HOST,
    run_benchmark,
    run_ragas,
    summarize_answer_relevancy,
)
from mededge_rag.schema import QARecord
from mededge_rag.vector_store import HashingVectorIndex


def sample_records() -> list[QARecord]:
    return [
        QARecord(
            qa_id="sample-001",
            domain="소아청소년과",
            q_type="응급상황",
            question="아이가 열이 높고 경련하면 어떻게 해야 하나요?",
            answer="고열과 경련이 동반되면 응급의료기관 방문이 필요합니다.",
        ),
        QARecord(
            qa_id="sample-008",
            domain="신경과",
            q_type="응급상황",
            question="갑자기 한쪽 팔에 힘이 빠지고 말이 어눌하면 어떻게 해야 하나요?",
            answer="뇌졸중 의심 증상일 수 있으므로 즉시 119 또는 응급의료기관에 연락해야 합니다.",
        ),
    ]


def build_sample_index(tmp_path: Path) -> Path:
    index_path = tmp_path / "index.json"
    index = HashingVectorIndex()
    index.add(sample_records())
    index.save(index_path)
    return index_path


def write_queries(tmp_path: Path) -> Path:
    queries_path = tmp_path / "queries.jsonl"
    queries_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "question": "아이가 열이 높고 경련하면 어떻게 해야 하나요?",
                        "expected_qa_id": "sample-001",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "question": "갑자기 한쪽 팔에 힘이 빠지고 말이 어눌하면 어떻게 해야 하나요?",
                        "expected_qa_id": "sample-008",
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return queries_path


def test_benchmark_writes_llm_only_and_rag_rows_with_gemma4_generation_model(tmp_path: Path, monkeypatch) -> None:
    class FakeClient:
        models: list[str] = []

        def __init__(self, host: str = "http://localhost:11434", model: str = DEFAULT_GENERATION_MODEL, timeout: float = 60.0) -> None:
            self.model = model
            self.host = host
            self.timeout = timeout
            FakeClient.models.append(model)

        def available(self) -> bool:
            return True

        def chat(self, system: str, prompt: str) -> str:
            return f"{self.model} generated answer"

    monkeypatch.setattr("mededge_rag.evaluation.OllamaClient", FakeClient)

    output_path = tmp_path / "benchmark.csv"
    rows = run_benchmark(
        index_path=str(build_sample_index(tmp_path)),
        queries_path=str(write_queries(tmp_path)),
        output_path=str(output_path),
    )

    assert output_path.is_file()
    assert {row["condition"] for row in rows} == {"llm_only", "rag_top3"}
    assert {row["generation_model"] for row in rows} == {DEFAULT_GENERATION_MODEL}
    assert {row["used_llm"] for row in rows} == {True}
    assert FakeClient.models and set(FakeClient.models) == {DEFAULT_GENERATION_MODEL}

    rag_rows = [row for row in rows if row["condition"] == "rag_top3"]
    llm_rows = [row for row in rows if row["condition"] == "llm_only"]
    assert all(row["hit_at_k"] is True for row in rag_rows)
    assert all(row["hit_at_k"] == "" for row in llm_rows)
    assert all(json.loads(row["contexts_json"]) for row in rag_rows)
    assert all(json.loads(row["contexts_json"]) == [] for row in llm_rows)


def test_ragas_writes_scores_with_default_ollama_cloud_gemini_judge(tmp_path: Path) -> None:
    benchmark_path = tmp_path / "benchmark.csv"
    with benchmark_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "condition",
                "question",
                "expected_qa_id",
                "reference",
                "answer",
                "contexts_json",
                "reference_contexts_json",
                "retrieved_ids",
                "hit_at_k",
                "latency_ms",
                "generation_model",
                "used_llm",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "condition": "llm_only",
                "question": "질문",
                "expected_qa_id": "sample-001",
                "reference": "정답",
                "answer": "답변",
                "contexts_json": "[]",
                "reference_contexts_json": "[]",
                "retrieved_ids": "",
                "hit_at_k": "",
                "latency_ms": "1",
                "generation_model": DEFAULT_GENERATION_MODEL,
                "used_llm": "false",
            }
        )
        writer.writerow(
            {
                "condition": "rag_top3",
                "question": "질문",
                "expected_qa_id": "sample-001",
                "reference": "정답",
                "answer": "답변",
                "contexts_json": json.dumps(["근거"], ensure_ascii=False),
                "reference_contexts_json": json.dumps(["정답 근거"], ensure_ascii=False),
                "retrieved_ids": "sample-001",
                "hit_at_k": "True",
                "latency_ms": "2",
                "generation_model": DEFAULT_GENERATION_MODEL,
                "used_llm": "true",
            }
        )

    seen_configs = []

    class FakeScore:
        def __init__(self, value: float) -> None:
            self.value = value

    class FakeScorer:
        def __init__(self, value: float) -> None:
            self.value = value

        def score(self, **kwargs) -> FakeScore:
            return FakeScore(self.value)

    def scorer_factory(config):
        seen_configs.append(config)
        return {
            "answer_relevancy": FakeScorer(0.81),
            "faithfulness": FakeScorer(0.92),
            "context_precision": FakeScorer(0.73),
            "context_recall": FakeScorer(0.64),
        }

    output_path = tmp_path / "ragas.csv"
    rows = run_ragas(str(benchmark_path), str(output_path), scorer_factory=scorer_factory)

    assert seen_configs[0].judge_model == DEFAULT_JUDGE_MODEL
    assert seen_configs[0].judge_host == DEFAULT_JUDGE_HOST
    assert output_path.is_file()
    assert rows[0]["answer_relevancy"] == 0.81
    assert rows[0]["faithfulness"] == ""
    assert rows[1]["faithfulness"] == 0.92
    assert rows[1]["context_precision"] == 0.73
    assert rows[1]["context_recall"] == 0.64


def test_ragas_can_run_answer_relevancy_only(tmp_path: Path) -> None:
    benchmark_path = tmp_path / "benchmark.csv"
    with benchmark_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "condition",
                "question",
                "expected_qa_id",
                "reference",
                "answer",
                "contexts_json",
                "reference_contexts_json",
                "retrieved_ids",
                "hit_at_k",
                "latency_ms",
                "generation_model",
                "used_llm",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "condition": "rag_top3",
                "question": "질문",
                "expected_qa_id": "sample-001",
                "reference": "정답",
                "answer": "답변",
                "contexts_json": json.dumps(["근거"], ensure_ascii=False),
                "reference_contexts_json": json.dumps(["정답 근거"], ensure_ascii=False),
                "retrieved_ids": "sample-001",
                "hit_at_k": "True",
                "latency_ms": "2",
                "generation_model": DEFAULT_GENERATION_MODEL,
                "used_llm": "true",
            }
        )

    called = []

    class FakeScore:
        def __init__(self, value: float) -> None:
            self.value = value

    class FakeScorer:
        def __init__(self, name: str, value: float) -> None:
            self.name = name
            self.value = value

        def score(self, **kwargs) -> FakeScore:
            called.append(self.name)
            return FakeScore(self.value)

    def scorer_factory(config, metrics):
        assert metrics == ["answer_relevancy"]
        return {
            "answer_relevancy": FakeScorer("answer_relevancy", 0.83),
            "faithfulness": FakeScorer("faithfulness", 0.11),
        }

    output_path = tmp_path / "ragas.csv"
    rows = run_ragas(str(benchmark_path), str(output_path), metrics=["answer_relevancy"], scorer_factory=scorer_factory)

    assert called == ["answer_relevancy"]
    assert rows[0]["answer_relevancy"] == 0.83
    assert "faithfulness" not in rows[0]


def test_summarize_answer_relevancy_writes_paired_delta_and_ci(tmp_path: Path) -> None:
    ragas_path = tmp_path / "ragas.csv"
    with ragas_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["condition", "question", "expected_qa_id", "answer_relevancy"],
        )
        writer.writeheader()
        writer.writerow({"condition": "llm_only", "question": "q1", "expected_qa_id": "a", "answer_relevancy": "0.40"})
        writer.writerow({"condition": "rag_top3", "question": "q1", "expected_qa_id": "a", "answer_relevancy": "0.70"})
        writer.writerow({"condition": "llm_only", "question": "q2", "expected_qa_id": "b", "answer_relevancy": "0.50"})
        writer.writerow({"condition": "rag_top3", "question": "q2", "expected_qa_id": "b", "answer_relevancy": "0.90"})

    delta_path = tmp_path / "delta.csv"
    summary_path = tmp_path / "summary.csv"
    summary = summarize_answer_relevancy(
        str(ragas_path),
        str(delta_path),
        str(summary_path),
        bootstrap_samples=200,
        seed=7,
    )

    assert delta_path.is_file()
    assert summary_path.is_file()
    assert summary["paired_n"] == 2
    assert summary["llm_only_mean"] == 0.45
    assert summary["rag_top3_mean"] == 0.8
    assert summary["delta_mean"] == 0.35
    assert 0.29 <= summary["delta_ci_low"] <= summary["delta_ci_high"] <= 0.41


def test_cli_exposes_benchmark_and_ragas_commands() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "mededge_rag.cli", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "eval" in result.stdout
    assert "ragas" in result.stdout
