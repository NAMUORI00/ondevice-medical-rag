from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

from .vector_store import SearchHit

DISCLAIMER = "본 답변은 연구용 의료 정보이며 진단이나 처방을 대체하지 않습니다. 증상이 심하거나 지속되면 의료진 또는 응급의료기관에 상담하세요."


@dataclass(slots=True)
class OllamaClient:
    host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model: str = os.getenv("OLLAMA_MODEL", "gemma4:e2b")
    timeout: float = 60.0

    def available(self) -> bool:
        try:
            with urllib.request.urlopen(self._request("/api/tags", method="GET"), timeout=3) as response:
                return response.status == 200
        except (OSError, urllib.error.URLError):
            return False

    def chat(self, system: str, prompt: str) -> str:
        body = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
        request = self._request(
            "/api/chat",
            data=json.dumps(body).encode("utf-8"),
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload.get("message", {}).get("content", "").strip()

    def _request(self, path: str, data: bytes | None = None, method: str = "POST") -> urllib.request.Request:
        headers = {"Content-Type": "application/json"}
        api_key = os.getenv("OLLAMA_API_KEY")
        if self.host.rstrip("/") == "https://ollama.com" and api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return urllib.request.Request(
            f"{self.host.rstrip('/')}{path}",
            data=data,
            headers=headers,
            method=method,
        )


def answer_question(question: str, hits: list[SearchHit], use_llm: bool = True) -> str:
    if use_llm:
        client = OllamaClient()
        if client.available():
            try:
                return _with_disclaimer(client.chat(system_prompt(), build_prompt(question, hits)))
            except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
                pass
    return template_answer(question, hits)


def system_prompt() -> str:
    return (
        "You are a Korean medical information QA assistant for a research prototype. "
        "Answer only from the provided evidence. Do not diagnose, prescribe, or tell users to delay emergency care. "
        "Cite evidence IDs and domains. Keep the answer concise."
    )


def build_prompt(question: str, hits: list[SearchHit]) -> str:
    evidence = []
    for idx, hit in enumerate(hits, start=1):
        record = hit.record
        evidence.append(
            "\n".join(
                [
                    f"[{idx}] qa_id={record.qa_id}",
                    f"domain={record.domain}",
                    f"q_type={record.q_type}",
                    f"question={record.question}",
                    f"answer={record.answer}",
                    f"score={hit.score:.4f}",
                ]
            )
        )
    return (
        f"사용자 질문: {question}\n\n"
        f"검색 근거:\n\n{chr(10).join(evidence)}\n\n"
        "요구사항:\n"
        "1. 한국어로 답변한다.\n"
        "2. 근거에 없는 내용을 단정하지 않는다.\n"
        "3. 마지막에 참조한 qa_id와 domain을 짧게 표시한다.\n"
        f"4. 다음 안전 문구를 포함한다: {DISCLAIMER}"
    )


def template_answer(question: str, hits: list[SearchHit]) -> str:
    if not hits:
        return _with_disclaimer("검색된 근거가 부족하여 답변을 생성할 수 없습니다.")

    lines = [f"질문: {question}", "", "검색된 근거를 바탕으로 보면:"]
    for hit in hits:
        record = hit.record
        lines.append(f"- {record.answer} (근거: {record.qa_id}, {record.domain}, score={hit.score:.3f})")
    return _with_disclaimer("\n".join(lines))


def _with_disclaimer(text: str) -> str:
    if DISCLAIMER in text:
        return text
    return f"{text.rstrip()}\n\n{DISCLAIMER}"
