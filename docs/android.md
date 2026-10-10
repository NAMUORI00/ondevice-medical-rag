# Android 온디바이스 데모 상세

[README로 돌아가기](../README.md)

## 빌드와 모델 준비

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
