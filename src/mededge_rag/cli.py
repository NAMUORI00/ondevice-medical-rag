from __future__ import annotations

import argparse
import json

from .evaluation import DEFAULT_GENERATION_MODEL, DEFAULT_JUDGE_HOST, DEFAULT_JUDGE_MODEL, run_benchmark, run_ragas, summarize_answer_relevancy
from .ingest import load_records, write_records
from .pipeline import ask
from .vector_store import HashingVectorIndex


def main() -> None:
    parser = argparse.ArgumentParser(prog="mededge-rag", description="MedEdge local RAG prototype")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Build a local vector index from QA JSON/JSONL")
    ingest_parser.add_argument("--input", required=True)
    ingest_parser.add_argument("--index", required=True)
    ingest_parser.add_argument("--normalized-output")
    ingest_parser.add_argument("--dims", type=int, default=4096)

    ask_parser = subparsers.add_parser("ask", help="Ask a question against the local index")
    ask_parser.add_argument("--index", required=True)
    ask_parser.add_argument("--question", required=True)
    ask_parser.add_argument("--top-k", type=int, default=3)
    ask_parser.add_argument("--no-llm", action="store_true")
    ask_parser.add_argument("--json", action="store_true")

    eval_parser = subparsers.add_parser("eval", help="Run llm-only vs RAG benchmark and write CSV")
    eval_parser.add_argument("--index", required=True)
    eval_parser.add_argument("--queries", required=True)
    eval_parser.add_argument("--output", required=True)
    eval_parser.add_argument("--top-k", type=int, default=3)
    eval_parser.add_argument("--generation-model", default=DEFAULT_GENERATION_MODEL)
    eval_parser.add_argument("--no-llm", action="store_true")

    ragas_parser = subparsers.add_parser("ragas", help="Score a benchmark CSV with RAGAS")
    ragas_parser.add_argument("--input", required=True)
    ragas_parser.add_argument("--output", required=True)
    ragas_parser.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL)
    ragas_parser.add_argument("--judge-host", default=DEFAULT_JUDGE_HOST)
    ragas_parser.add_argument("--embedding-model", default="")
    ragas_parser.add_argument("--embedding-host", default=DEFAULT_JUDGE_HOST)
    ragas_parser.add_argument("--metrics", default=",".join(["answer_relevancy", "faithfulness", "context_precision", "context_recall"]))

    relevancy_parser = subparsers.add_parser("relevancy-delta", help="Summarize paired Answer Relevancy delta and CI")
    relevancy_parser.add_argument("--input", required=True)
    relevancy_parser.add_argument("--delta-output", required=True)
    relevancy_parser.add_argument("--summary-output", required=True)
    relevancy_parser.add_argument("--baseline-condition", default="llm_only")
    relevancy_parser.add_argument("--rag-condition", default="rag_top3")
    relevancy_parser.add_argument("--confidence", type=float, default=0.95)
    relevancy_parser.add_argument("--bootstrap-samples", type=int, default=10000)
    relevancy_parser.add_argument("--seed", type=int, default=13)

    args = parser.parse_args()

    if args.command == "ingest":
        records = load_records(args.input)
        index = HashingVectorIndex(dims=args.dims)
        index.add(records)
        index.save(args.index)
        if args.normalized_output:
            write_records(records, args.normalized_output)
        print(f"Indexed {len(records)} records -> {args.index}")
    elif args.command == "ask":
        answer, evidence = ask(args.index, args.question, top_k=args.top_k, use_llm=not args.no_llm)
        if args.json:
            print(json.dumps({"answer": answer, "evidence": evidence}, ensure_ascii=False, indent=2))
        else:
            print(answer)
            print("\nEvidence:")
            for item in evidence:
                print(f"- {item['qa_id']} | {item['domain']} | {item['q_type']} | score={item['score']}")
    elif args.command == "eval":
        run_benchmark(
            args.index,
            args.queries,
            args.output,
            top_k=args.top_k,
            generation_model=args.generation_model,
            use_llm=not args.no_llm,
        )
        print(f"Wrote benchmark results -> {args.output}")
    elif args.command == "ragas":
        run_ragas(
            args.input,
            args.output,
            judge_model=args.judge_model,
            judge_host=args.judge_host,
            embedding_model=args.embedding_model,
            embedding_host=args.embedding_host,
            metrics=[metric.strip() for metric in args.metrics.split(",")],
        )
        print(f"Wrote RAGAS results -> {args.output}")
    elif args.command == "relevancy-delta":
        summary = summarize_answer_relevancy(
            args.input,
            args.delta_output,
            args.summary_output,
            baseline_condition=args.baseline_condition,
            rag_condition=args.rag_condition,
            confidence=args.confidence,
            bootstrap_samples=args.bootstrap_samples,
            seed=args.seed,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
