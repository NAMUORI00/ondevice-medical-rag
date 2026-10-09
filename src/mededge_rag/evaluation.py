from __future__ import annotations

import csv
import inspect
import json
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .generation import DISCLAIMER, OllamaClient, build_prompt, system_prompt, template_answer
from .vector_store import HashingVectorIndex, SearchHit

DEFAULT_GENERATION_MODEL = "gemma4:e2b"
DEFAULT_JUDGE_MODEL = "gemini-3-flash-preview:cloud"
DEFAULT_JUDGE_HOST = "https://ollama.com/v1"

BENCHMARK_FIELDS = [
    "condition",
    "question",
    "expected_qa_id",
    "reference",
    "answer",
    "contexts_json",
    "reference_contexts_json",
    "retrieved_ids",
    "hit_at_1",
    "hit_at_k",
    "latency_ms",
    "generation_model",
    "used_llm",
]

RAGAS_METRICS = [
    "answer_relevancy",
    "faithfulness",
    "context_precision",
    "context_recall",
]


@dataclass(slots=True)
class RagasConfig:
    judge_model: str = DEFAULT_JUDGE_MODEL
    judge_host: str = DEFAULT_JUDGE_HOST
    embedding_model: str = ""
    embedding_host: str = DEFAULT_JUDGE_HOST
    api_key: str = ""


def run_benchmark(
    index_path: str,
    queries_path: str,
    output_path: str,
    top_k: int = 3,
    generation_model: str = DEFAULT_GENERATION_MODEL,
    use_llm: bool = True,
) -> list[dict[str, Any]]:
    index = HashingVectorIndex.load(index_path)
    records_by_id = {record.qa_id: record for record in index.records}
    rows: list[dict[str, Any]] = []

    for item in load_queries(queries_path):
        question = item["question"]
        expected_id = str(item.get("expected_qa_id", ""))
        expected_record = records_by_id.get(expected_id)
        reference = str(item.get("reference") or (expected_record.answer if expected_record else ""))
        reference_contexts = []
        if expected_record:
            reference_contexts.append(record_context(expected_record))

        rows.append(
            benchmark_row(
                condition="llm_only",
                question=question,
                expected_id=expected_id,
                reference=reference,
                reference_contexts=reference_contexts,
                hits=[],
                generation_model=generation_model,
                use_llm=use_llm,
                top_k=top_k,
            )
        )

        hits = index.search(question, top_k=top_k)
        rows.append(
            benchmark_row(
                condition=f"rag_top{top_k}",
                question=question,
                expected_id=expected_id,
                reference=reference,
                reference_contexts=reference_contexts,
                hits=hits,
                generation_model=generation_model,
                use_llm=use_llm,
                top_k=top_k,
            )
        )

    write_csv(rows, output_path, BENCHMARK_FIELDS)
    return rows


def run_ragas(
    benchmark_path: str,
    output_path: str,
    judge_model: str = DEFAULT_JUDGE_MODEL,
    judge_host: str = DEFAULT_JUDGE_HOST,
    embedding_model: str = "",
    embedding_host: str = DEFAULT_JUDGE_HOST,
    api_key: str = "",
    metrics: list[str] | None = None,
    scorer_factory: Callable[..., dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    selected_metrics = normalize_metrics(metrics)
    config = RagasConfig(
        judge_model=judge_model,
        judge_host=judge_host,
        embedding_model=embedding_model,
        embedding_host=embedding_host,
        api_key=api_key,
    )
    if scorer_factory:
        scorer_params = inspect.signature(scorer_factory).parameters
        scorers = scorer_factory(config, selected_metrics) if len(scorer_params) > 1 else scorer_factory(config)
    else:
        scorers = build_ragas_scorers(config, selected_metrics)
    rows = read_csv(benchmark_path)
    output_rows: list[dict[str, Any]] = []

    for row in rows:
        contexts = parse_json_list(row.get("contexts_json", "[]"))
        result = dict(row)
        result["judge_model"] = judge_model
        result["judge_host"] = judge_host
        for metric in selected_metrics:
            result[metric] = ""

        if "answer_relevancy" in selected_metrics and "answer_relevancy" in scorers:
            result["answer_relevancy"] = score_metric(
                scorers["answer_relevancy"],
                user_input=row["question"],
                response=row["answer"],
            )

        if contexts:
            if "faithfulness" in selected_metrics and "faithfulness" in scorers:
                result["faithfulness"] = score_metric(
                    scorers["faithfulness"],
                    user_input=row["question"],
                    response=row["answer"],
                    retrieved_contexts=contexts,
                )
            if "context_precision" in selected_metrics and "context_precision" in scorers:
                result["context_precision"] = score_metric(
                    scorers["context_precision"],
                    user_input=row["question"],
                    reference=row.get("reference", ""),
                    retrieved_contexts=contexts,
                )
            if "context_recall" in selected_metrics and "context_recall" in scorers:
                result["context_recall"] = score_metric(
                    scorers["context_recall"],
                    user_input=row["question"],
                    reference=row.get("reference", ""),
                    retrieved_contexts=contexts,
                )

        output_rows.append(result)

    fields = list(rows[0].keys()) if rows else BENCHMARK_FIELDS
    write_csv(output_rows, output_path, fields + ["judge_model", "judge_host", *selected_metrics])
    return output_rows


def summarize_answer_relevancy(
    ragas_path: str,
    delta_output_path: str,
    summary_output_path: str,
    baseline_condition: str = "llm_only",
    rag_condition: str = "rag_top3",
    confidence: float = 0.95,
    bootstrap_samples: int = 10000,
    seed: int = 13,
) -> dict[str, Any]:
    rows = read_csv(ragas_path)
    pairs: dict[str, dict[str, Any]] = {}

    for row in rows:
        condition = row.get("condition", "")
        if condition not in {baseline_condition, rag_condition}:
            continue
        score = parse_float(row.get("answer_relevancy", ""))
        if score is None:
            continue
        pair_id = row.get("expected_qa_id") or row.get("question", "")
        if not pair_id:
            continue
        item = pairs.setdefault(
            pair_id,
            {
                "pair_id": pair_id,
                "question": row.get("question", ""),
                "expected_qa_id": row.get("expected_qa_id", ""),
            },
        )
        item[condition] = score

    paired_rows = []
    deltas = []
    baseline_scores = []
    rag_scores = []
    for item in pairs.values():
        if baseline_condition not in item or rag_condition not in item:
            continue
        baseline_score = float(item[baseline_condition])
        rag_score = float(item[rag_condition])
        delta = rag_score - baseline_score
        baseline_scores.append(baseline_score)
        rag_scores.append(rag_score)
        deltas.append(delta)
        paired_rows.append(
            {
                "pair_id": item["pair_id"],
                "question": item["question"],
                "expected_qa_id": item["expected_qa_id"],
                f"{baseline_condition}_answer_relevancy": round(baseline_score, 6),
                f"{rag_condition}_answer_relevancy": round(rag_score, 6),
                "answer_relevancy_delta": round(delta, 6),
            }
        )

    ci_low, ci_high = bootstrap_mean_ci(deltas, confidence=confidence, samples=bootstrap_samples, seed=seed)
    summary = {
        "baseline_condition": baseline_condition,
        "rag_condition": rag_condition,
        "paired_n": len(deltas),
        "llm_only_mean": round(mean(baseline_scores), 6),
        "rag_top3_mean": round(mean(rag_scores), 6),
        "delta_mean": round(mean(deltas), 6),
        "confidence": confidence,
        "delta_ci_low": round(ci_low, 6),
        "delta_ci_high": round(ci_high, 6),
        "bootstrap_samples": bootstrap_samples,
    }

    write_csv(
        paired_rows,
        delta_output_path,
        [
            "pair_id",
            "question",
            "expected_qa_id",
            f"{baseline_condition}_answer_relevancy",
            f"{rag_condition}_answer_relevancy",
            "answer_relevancy_delta",
        ],
    )
    write_csv([summary], summary_output_path, list(summary.keys()))
    return summary


def load_queries(path: str | Path) -> list[dict[str, Any]]:
    queries: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                queries.append(json.loads(line))
    return queries


def benchmark_row(
    condition: str,
    question: str,
    expected_id: str,
    reference: str,
    reference_contexts: list[str],
    hits: list[SearchHit],
    generation_model: str,
    use_llm: bool,
    top_k: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    answer, used_llm = generate_answer(question, hits, condition=condition, model=generation_model, use_llm=use_llm)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    contexts = [record_context(hit.record) for hit in hits]
    retrieved_ids = [hit.record.qa_id for hit in hits]
    hit_at_k = expected_id in retrieved_ids if expected_id and retrieved_ids else ""
    return {
        "condition": condition,
        "question": question,
        "expected_qa_id": expected_id,
        "reference": reference,
        "answer": answer,
        "contexts_json": json.dumps(contexts, ensure_ascii=False),
        "reference_contexts_json": json.dumps(reference_contexts, ensure_ascii=False),
        "retrieved_ids": "|".join(retrieved_ids),
        "hit_at_1": retrieved_ids[0] == expected_id if expected_id and retrieved_ids else "",
        "hit_at_k": hit_at_k,
        "latency_ms": elapsed_ms,
        "generation_model": generation_model,
        "used_llm": used_llm,
    }


def generate_answer(question: str, hits: list[SearchHit], condition: str, model: str, use_llm: bool) -> tuple[str, bool]:
    if not use_llm:
        if hits:
            return template_answer(question, hits), False
        return with_disclaimer("로컬 LLM 호출을 비활성화한 연결 이전 조건입니다."), False

    client = OllamaClient(model=model)
    if client.available():
        try:
            if hits:
                return with_disclaimer(client.chat(system_prompt(), build_prompt(question, hits))), True
            return with_disclaimer(client.chat(llm_only_system_prompt(), llm_only_prompt(question))), True
        except (OSError, TimeoutError, json.JSONDecodeError):
            pass

    if hits:
        return template_answer(question, hits), False
    return with_disclaimer(f"{condition} 조건에서 로컬 LLM을 사용할 수 없어 답변을 생성하지 못했습니다."), False


def llm_only_system_prompt() -> str:
    return (
        "You are a Korean medical information QA assistant for a research prototype. "
        "Answer from the local model only, without retrieved evidence. Do not diagnose, prescribe, or tell users to delay emergency care. "
        "Keep the answer concise and include the required safety notice."
    )


def llm_only_prompt(question: str) -> str:
    return (
        f"사용자 질문: {question}\n\n"
        "요구사항:\n"
        "1. 한국어로 답변한다.\n"
        "2. 확실하지 않은 내용은 단정하지 않는다.\n"
        f"3. 다음 안전 문구를 포함한다: {DISCLAIMER}"
    )


def record_context(record: Any) -> str:
    return "\n".join(
        [
            f"qa_id={record.qa_id}",
            f"domain={record.domain}",
            f"q_type={record.q_type}",
            f"question={record.question}",
            f"answer={record.answer}",
        ]
    )


def with_disclaimer(text: str) -> str:
    if DISCLAIMER in text:
        return text
    return f"{text.rstrip()}\n\n{DISCLAIMER}"


def build_ragas_scorers(config: RagasConfig, metrics: list[str] | None = None) -> dict[str, Any]:
    selected_metrics = set(normalize_metrics(metrics))
    api_key = config.api_key or os.getenv("OLLAMA_API_KEY", "")
    if "ollama.com" in config.judge_host and not api_key:
        raise RuntimeError("Set OLLAMA_API_KEY before running RAGAS with Ollama Cloud.")

    try:
        from openai import AsyncOpenAI
        from ragas.llms import llm_factory
    except ImportError as error:
        raise RuntimeError('Install RAGAS dependencies with: python -m pip install -e ".[eval]"') from error

    client = AsyncOpenAI(api_key=api_key or "ollama", base_url=config.judge_host)
    llm = llm_factory(config.judge_model, client=client, temperature=0, max_tokens=8192)
    scorers: dict[str, Any] = {}

    context_metrics = selected_metrics & {"faithfulness", "context_precision", "context_recall"}
    if context_metrics:
        try:
            from ragas.metrics.collections import ContextPrecision, ContextRecall, Faithfulness
        except ImportError as error:
            raise RuntimeError('Install RAGAS dependencies with: python -m pip install -e ".[eval]"') from error
        if "faithfulness" in context_metrics:
            scorers["faithfulness"] = Faithfulness(llm=llm)
        if "context_precision" in context_metrics:
            scorers["context_precision"] = ContextPrecision(llm=llm)
        if "context_recall" in context_metrics:
            scorers["context_recall"] = ContextRecall(llm=llm)

    if "answer_relevancy" in selected_metrics:
        if not config.embedding_model:
            raise RuntimeError("Set --embedding-model before running answer_relevancy.")
        try:
            from ragas.embeddings.base import embedding_factory
            from ragas.metrics.collections import AnswerRelevancy
        except ImportError as error:
            raise RuntimeError('Install RAGAS dependencies with: python -m pip install -e ".[eval]"') from error
        embedding_client = AsyncOpenAI(api_key=api_key or "ollama", base_url=config.embedding_host)
        embeddings = embedding_factory("openai", model=config.embedding_model, client=embedding_client)
        scorers["answer_relevancy"] = AnswerRelevancy(llm=llm, embeddings=embeddings)

    return scorers


def normalize_metrics(metrics: list[str] | None) -> list[str]:
    if metrics is None:
        return list(RAGAS_METRICS)
    selected = []
    for metric in metrics:
        name = metric.strip()
        if not name:
            continue
        if name not in RAGAS_METRICS:
            raise ValueError(f"Unsupported RAGAS metric: {name}")
        if name not in selected:
            selected.append(name)
    return selected


def score_metric(scorer: Any, **kwargs: Any) -> Any:
    result = scorer.score(**kwargs) if hasattr(scorer, "score") else scorer(**kwargs)
    return result.value if hasattr(result, "value") else result


def parse_json_list(value: str) -> list[str]:
    if not value:
        return []
    parsed = json.loads(value)
    return parsed if isinstance(parsed, list) else []


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def parse_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def bootstrap_mean_ci(deltas: list[float], confidence: float, samples: int, seed: int) -> tuple[float, float]:
    if not deltas:
        return 0.0, 0.0
    if len(deltas) == 1 or samples <= 0:
        value = mean(deltas)
        return value, value

    rng = random.Random(seed)
    bootstrap_means = []
    n = len(deltas)
    for _ in range(samples):
        bootstrap_means.append(sum(deltas[rng.randrange(n)] for _ in range(n)) / n)
    bootstrap_means.sort()

    tail = (1.0 - confidence) / 2.0
    low_index = int(tail * (samples - 1))
    high_index = int((1.0 - tail) * (samples - 1))
    return bootstrap_means[low_index], bootstrap_means[high_index]


def write_csv(rows: list[dict[str, Any]], path: str | Path, fieldnames: list[str]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
