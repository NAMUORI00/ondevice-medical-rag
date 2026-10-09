# KIIT 2026 MedEdge RAG

온디바이스 소형 LLM과 로컬 의료 지식 RAG를 결합한 한국어 의료 질의응답 프로토타입입니다.

이 프로젝트는 한국정보기술학회 2026 하계종합학술대회에서 발표되었습니다(제1저자).

이 저장소는 AIHub 의료 QA 데이터셋과 로컬 Gemma4 모델만 준비되면 바로 실험할 수 있도록 구성했습니다. API 키, 원본 데이터, 샘플 데이터, 모델 가중치는 저장소에 포함하지 않습니다. AIHub 데이터는 재배포하지 않으므로 AIHub에서 이용 신청 후 직접 받아 로컬에 두어야 합니다.

## 핵심 방향

- 최종 데모는 Android 기기에서 실행되는 Gemma 4 E2B `.litertlm` 모델을 기본 목표로 합니다.
- 질문, 검색 근거, 생성 프롬프트는 외부 LLM API로 전송하지 않는 구조를 우선합니다.
- Python/Ollama 경로는 개발용 로컬 검증 경로이며, Android 데모는 Google AI Edge LiteRT-LM Kotlin API를 사용합니다.
- Ollama Cloud와 Hugging Face API는 선택적 인제스트 보조 용도입니다.
- 구현은 `AGENTS.md`의 Karpathy-style 지침에 맞춰 가정을 드러내고, 최소 코드로 만들고, 검증 가능한 작은 루프로 유지합니다.

## Android 온디바이스 데모

`android/MedEdgeRag`는 Android 온디바이스 데모입니다. 앱은 로컬에서 제공한 QA 자산을 해시 벡터 인덱스로 검색한 뒤 앱 내부 저장소 또는 `/data/local/tmp/llm/gemma-4-E2B-it.litertlm`의 Gemma 4 E2B 모델을 LiteRT-LM `Engine`으로 호출합니다.

두 배포 flavor를 분리합니다.

- `offline`: `android.permission.INTERNET`을 선언하지 않는 온디바이스 증명용 빌드입니다. 모델은 ADB로 사전 배치합니다.
- `bootstrap`: 발표와 사용자 편의를 위한 초기 설정 빌드입니다. 첫 실행에서 모델을 다운로드하고 SHA-256 검증 후 앱 내부 저장소에 저장합니다. 다운로드 이후 추론은 로컬 모델만 사용합니다.

사용자 편의용 초기 버전은 `bootstrap` 빌드의 `Gemma4 모델 다운로드` 버튼으로 모델을 앱 내부 저장소에 준비합니다. 온디바이스 증명용 `offline` 빌드는 인터넷 권한이 없으므로 개발 PC에서 ADB로 모델을 사전 배치합니다.

Gemma 4 모델 가중치는 저장소에 포함하지 않습니다. Google 문서 기준으로 Gemma 4는 Kaggle 또는 Hugging Face에서 받을 수 있으며, 기본 소스 모델은 instruction-tuned `google/gemma-4-E2B-it`입니다. Android 앱은 LiteRT-LM이 읽을 수 있는 `.litertlm` 모델 파일을 사용합니다. 빠른 경로는 LiteRT Community의 `litert-community/gemma-4-E2B-it-litert-lm`에서 `gemma-4-E2B-it.litertlm`를 받아 쓰는 것입니다.

모델 다운로드는 저장소 밖 비공개 산출물로 유지합니다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\download_gemma4_litert_model.ps1
```

로컬 검증은 일반적인 폰 모델인 Pixel 7 (`pixel_7`) 기반 Android 15/API 35 Google APIs x86_64 에뮬레이터로 맞춥니다. AVD 이름은 `MedEdge_Pixel_7_API_35`입니다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\create_android_emulator.ps1
powershell -ExecutionPolicy Bypass -File scripts\run_android_emulator_check.ps1 -CreateAvd
```

```powershell
adb shell mkdir -p /data/local/tmp/llm/
adb push .\models\gemma-4-E2B-it.litertlm /data/local/tmp/llm/gemma-4-E2B-it.litertlm
cd android\MedEdgeRag
.\gradlew.bat :app:assembleOfflineDebug
.\gradlew.bat :app:assembleBootstrapDebug
```

모델 파일이 없으면 앱은 외부 호출 없이 검색 근거 기반 템플릿 답변으로 폴백합니다.

Android 툴체인과 `adb`가 준비된 PC에서는 다음 검증 스크립트로 인터넷 권한 부재, APK 빌드, 기기 내 모델 파일 존재를 함께 확인합니다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_android_ondevice_check.ps1
powershell -ExecutionPolicy Bypass -File scripts\run_android_ondevice_check.ps1 -LocalModelFile .\models\gemma-4-E2B-it.litertlm
powershell -ExecutionPolicy Bypass -File scripts\run_android_ondevice_check.ps1 -InstallApk -LaunchApp
powershell -ExecutionPolicy Bypass -File scripts\run_android_ondevice_check.ps1 -LocalModelFile .\models\gemma-4-E2B-it.litertlm -InstallApk -RunSmokeTest
powershell -ExecutionPolicy Bypass -File scripts\run_android_bootstrap_check.ps1
powershell -ExecutionPolicy Bypass -File scripts\run_android_bootstrap_check.ps1 -InstallApk -RunDownloadTest
```

## 빠른 시작

샘플 QA는 저장소에 커밋하지 않습니다. 로컬에서 `data/sample/medical_qa_sample.jsonl`을 준비한 뒤 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m mededge_rag.cli ingest --input data/sample/medical_qa_sample.jsonl --index data/index/mededge_index.json
python -m mededge_rag.cli ask --index data/index/mededge_index.json --question "아이가 고열일 때 언제 응급실에 가야 하나요?"
python -m mededge_rag.cli eval --index data/index/mededge_index.json --queries experiments/queries.jsonl --output experiments/benchmark.csv
```

Windows PowerShell에서 한글 출력이 깨지면 검증용 스크립트를 사용할 수 있습니다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_index.ps1
powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1
powershell -ExecutionPolicy Bypass -File scripts\evaluate.ps1
```

Ollama가 설치되어 있고 모델이 준비되어 있으면 Python 개발 경로의 생성 단계에서 로컬 LLM을 호출합니다.

```powershell
ollama pull gemma4:e2b
$env:OLLAMA_MODEL="gemma4:e2b"
python -m mededge_rag.cli ask --index data/index/mededge_index.json --question "임신 중 복통이 있으면 어떻게 해야 하나요?"
```

Ollama가 없거나 실행 중이 아니면 검색된 근거 기반 템플릿 답변으로 안전하게 폴백합니다.

## Ollama Cloud 보조 생성

Cloud는 최종 온디바이스 데모가 아니라 보조 생성용입니다.

```powershell
$env:OLLAMA_HOST="https://ollama.com"
$env:OLLAMA_MODEL="gemma3:4b"
$env:OLLAMA_API_KEY="..."
python -m mededge_rag.cli ask --index data/index/aihub_required_sample_index.json --question "임신 중 복통이 있으면 어떻게 해야 하나요?"
```

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

## 실제 데이터 연결

AIHub 원본 데이터는 `data/raw/`에 둡니다. JSON 배열, JSONL, 또는 하위 구조에 `qa_id`, `domain`, `q_type`, `question`, `answer` 필드가 있으면 로더가 정규화합니다.

```powershell
python -m mededge_rag.cli ingest --input data/raw/aihub_medical.json --index data/index/aihub_index.json
```

AIHub가 제공한 샘플 zip도 직접 인제스트할 수 있습니다.

```powershell
python -m mededge_rag.cli ingest --input "$HOME\Downloads\Sample.zip" --index data/index/aihub_required_sample_index.json
python -m mededge_rag.cli ingest --input "$HOME\Downloads\Sample (1).zip" --index data/index/aihub_expert_sample_index.json
```

현재 제공된 공식 샘플 기준 인제스트 결과:

- `Sample.zip`: 192 QA records
- `Sample (1).zip`: 153 QA records

## Streamlit 데모

```powershell
python -m pip install -e ".[app]"
streamlit run src/mededge_rag/app/streamlit_app.py
```

## 환경 변수

`.env.example`을 참고하세요. 최종 온디바이스 데모에는 API 키가 필요하지 않습니다.

## 산출물

- `src/mededge_rag/`: RAG 프로토타입 코드
- `data/`: 로컬 전용 데이터와 인덱스 위치, Git에는 `.gitkeep`만 유지
- `experiments/queries.jsonl`: `llm_only`와 `rag_top3` 벤치마크 질의
- `android/MedEdgeRag/`: Android 완전 온디바이스 Gemma4 RAG 데모

## 의료 안전 문구

본 시스템은 연구용 의료 정보 보조 도구입니다. 진단, 처방, 응급 판단을 대체하지 않으며, 증상이 심하거나 지속되면 의료진 또는 응급의료기관에 상담해야 합니다.
