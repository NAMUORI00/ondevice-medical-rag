# 평가와 데이터 연결

[README로 돌아가기](../README.md)

## RAGAS 평가

벤치마크는 `llm_only`와 `rag_top3` 두 조건을 같은 `gemma4:e2b` 답변 생성 모델로 비교합니다. RAGAS judge는 기본값으로 Ollama Cloud의 OpenAI-compatible endpoint와 `gemini-3-flash-preview:cloud`를 사용합니다.

```powershell
python -m pip install -e ".[eval]"
powershell -ExecutionPolicy Bypass -File scripts\evaluate.ps1
powershell -ExecutionPolicy Bypass -File scripts\evaluate_ragas.ps1 -JudgeHost http://localhost:11434/v1 -JudgeModel gemini-3-flash-preview:cloud -EmbeddingHost http://localhost:11434/v1 -EmbeddingModel nomic-embed-text
```

Ollama Cloud REST endpoint를 직접 쓰려면 `OLLAMA_API_KEY`를 설정하고 기본 `JudgeHost=https://ollama.com/v1`을 사용합니다.

```powershell
$env:OLLAMA_API_KEY="..."
powershell -ExecutionPolicy Bypass -File scripts\evaluate_ragas.ps1 -EmbeddingModel nomic-embed-text
```

## 선택: 클라우드 보조 생성 (개발용)

Cloud는 최종 온디바이스 데모가 아니라 보조 생성용입니다.

```powershell
$env:OLLAMA_HOST="https://ollama.com"
$env:OLLAMA_MODEL="gemma3:4b"
$env:OLLAMA_API_KEY="..."
python -m mededge_rag.cli ask --index data/index/aihub_required_sample_index.json --question "임신 중 복통이 있으면 어떻게 해야 하나요?"
```

## 실제 데이터 연결

AIHub 원본 데이터는 `data/raw/`에 둡니다. JSON 배열, JSONL, 또는 하위 구조에 `qa_id`, `domain`, `q_type`, `question`, `answer` 필드가 있으면 로더가 정규화합니다.

```powershell
python -m mededge_rag.cli ingest --input data/raw/aihub_medical.json --index data/index/aihub_index.json
```

AIHub가 제공한 샘플 zip도 직접 인제스트할 수 있습니다.

```powershell
python -m mededge_rag.cli ingest --input <AIHub 필수 샘플 zip 경로> --index data/index/aihub_required_sample_index.json
python -m mededge_rag.cli ingest --input <AIHub 전문가 샘플 zip 경로> --index data/index/aihub_expert_sample_index.json
```

