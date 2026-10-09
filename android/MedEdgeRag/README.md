# MedEdge RAG Android

Android 온디바이스 데모입니다. 앱은 로컬 QA 자산 검색과 로컬 Gemma4 생성을 사용합니다. QA 샘플/풀데이터는 저장소에 커밋하지 않고 로컬 파일로만 준비합니다.

## 빌드 flavor

- `offline`: 네트워크 권한을 선언하지 않는 온디바이스 증명용 빌드입니다. 모델은 ADB로 사전 배치합니다.
- `bootstrap`: 발표와 사용자 편의를 위한 초기 설정 빌드입니다. 첫 실행에서 모델을 다운로드하고 SHA-256 검증 후 앱 내부 저장소에 저장합니다. 다운로드 이후 추론은 로컬 모델만 사용합니다.

## 모델 파일

Gemma 4 E2B의 Android 실행용 `.litertlm` 파일을 기기에 직접 배치합니다. 모델 파일은 크고 라이선스 확인이 필요하므로 저장소에 포함하지 않습니다.

Gemma 4 모델 가중치는 Google 문서의 Kaggle 또는 Hugging Face 경로에서 준비합니다. 기본 소스 모델은 instruction-tuned `google/gemma-4-E2B-it`입니다. 앱은 LiteRT-LM이 읽을 수 있는 `.litertlm` 파일을 지원합니다. 빠른 경로는 LiteRT Community의 `litert-community/gemma-4-E2B-it-litert-lm`에서 `gemma-4-E2B-it.litertlm`를 받아 쓰는 것입니다.

저장소 루트에서 다음 명령으로 LiteRT Community 모델을 `models\gemma-4-E2B-it.litertlm`에 받을 수 있습니다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\download_gemma4_litert_model.ps1
```

로컬 에뮬레이터 검증은 일반적인 폰 모델인 Pixel 7 (`pixel_7`) 기반 Android 15/API 35 Google APIs x86_64 AVD로 진행합니다. AVD 이름은 `MedEdge_Pixel_7_API_35`입니다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\create_android_emulator.ps1
powershell -ExecutionPolicy Bypass -File scripts\run_android_emulator_check.ps1 -CreateAvd
```

사용자 편의용 `bootstrap` 빌드는 앱의 `Gemma4 모델 다운로드` 버튼으로 모델을 앱 내부 저장소에 준비합니다. 온디바이스 증명용 `offline` 빌드는 인터넷 권한이 없으므로 ADB로 같은 모델을 배치합니다.

```powershell
adb shell mkdir -p /data/local/tmp/llm/
adb push .\models\gemma-4-E2B-it.litertlm /data/local/tmp/llm/gemma-4-E2B-it.litertlm
```

앱은 먼저 앱 내부 저장소의 `models/gemma-4-E2B-it.litertlm`를 확인하고, 없으면 `/data/local/tmp/llm/gemma-4-E2B-it.litertlm`를 확인합니다. 파일이 없으면 앱은 네트워크를 호출하지 않고, 로컬 검색 근거 기반 템플릿 답변으로 폴백합니다.

## 빌드

앱 실행용 QA 자산은 로컬에서 `app\src\main\assets\medical_qa_sample.jsonl`에 준비합니다. 이 파일은 Git 추적 대상이 아닙니다.

```powershell
cd android\MedEdgeRag
.\gradlew.bat :app:assembleOfflineDebug
.\gradlew.bat :app:assembleBootstrapDebug
```

로컬에는 JDK, Android SDK, Gradle 또는 Android Studio가 필요합니다.

저장소 루트에서는 다음 명령으로 APK 빌드, APK 권한 검사, 기기 내 모델 파일 확인, 설치와 실행을 한 번에 검증할 수 있습니다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_android_ondevice_check.ps1 -LocalModelFile .\models\gemma-4-E2B-it.litertlm -InstallApk -RunSmokeTest
powershell -ExecutionPolicy Bypass -File scripts\run_android_bootstrap_check.ps1 -InstallApk -RunDownloadTest
```
