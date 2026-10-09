from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "android" / "MedEdgeRag"


def test_android_project_has_ondevice_llm_and_no_network_permission() -> None:
    manifest = ANDROID / "app" / "src" / "main" / "AndroidManifest.xml"
    build_file = ANDROID / "app" / "build.gradle.kts"
    root_build_file = ANDROID / "build.gradle.kts"
    llm_engine = ANDROID / "app" / "src" / "main" / "java" / "com" / "mededge" / "rag" / "LiteRtGemmaEngine.kt"
    model_store = ANDROID / "app" / "src" / "main" / "java" / "com" / "mededge" / "rag" / "LocalModelStore.kt"

    manifest_text = manifest.read_text(encoding="utf-8")
    build_text = build_file.read_text(encoding="utf-8")
    root_build_text = root_build_file.read_text(encoding="utf-8")
    llm_text = llm_engine.read_text(encoding="utf-8")
    store_text = model_store.read_text(encoding="utf-8")

    assert "android.permission.INTERNET" not in manifest_text
    assert 'android:usesCleartextTraffic="false"' in manifest_text
    assert "com.google.ai.edge.litertlm:litertlm-android:0.11.0" in build_text
    assert 'id("org.jetbrains.kotlin.android") version "2.3.21"' in root_build_text
    assert "com.google.mediapipe:tasks-genai" not in build_text
    assert "com.google.ai.edge.litertlm.Engine" in llm_text
    assert "com.google.ai.edge.litertlm.EngineConfig" in llm_text
    assert "Backend.CPU()" in llm_text
    assert "createConversation" in llm_text
    assert "sendMessage" in llm_text
    assert "renderMessageIntoString" in llm_text
    assert "@OptIn(ExperimentalApi::class)" in llm_text
    assert "gemma-4-E2B-it.litertlm" in store_text
    assert "/data/local/tmp/llm/gemma-4-E2B-it.litertlm" in store_text
    assert "gemma4-e2b.task" not in store_text
    assert "context.filesDir" in store_text
    assert "importFromUri" not in store_text


def test_android_gradle_defines_offline_and_bootstrap_flavors() -> None:
    build_file = ANDROID / "app" / "build.gradle.kts"
    build_text = build_file.read_text(encoding="utf-8")

    assert 'flavorDimensions += "distribution"' in build_text
    assert 'create("offline")' in build_text
    assert 'create("bootstrap")' in build_text
    assert 'buildConfigField("boolean", "MODEL_BOOTSTRAP_ENABLED", "false")' in build_text
    assert 'buildConfigField("boolean", "MODEL_BOOTSTRAP_ENABLED", "true")' in build_text
    assert 'buildConfigField("String", "MODEL_DOWNLOAD_URL"' in build_text
    assert "b4f4f4df93418ddb4aa7da8bf33b584602a5b9f8" in build_text
    assert 'buildConfigField("String", "MODEL_SHA256"' in build_text
    assert "181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c" in build_text


def test_bootstrap_manifest_is_only_source_with_internet_permission() -> None:
    main_manifest = ANDROID / "app" / "src" / "main" / "AndroidManifest.xml"
    bootstrap_manifest = ANDROID / "app" / "src" / "bootstrap" / "AndroidManifest.xml"

    assert "android.permission.INTERNET" not in main_manifest.read_text(encoding="utf-8")
    assert 'android:name="android.permission.INTERNET"' in bootstrap_manifest.read_text(encoding="utf-8")


def test_android_rag_asset_path_and_kotlin_search_exist() -> None:
    index = ANDROID / "app" / "src" / "main" / "java" / "com" / "mededge" / "rag" / "HashingVectorIndex.kt"
    engine = ANDROID / "app" / "src" / "main" / "java" / "com" / "mededge" / "rag" / "MedEdgeRagEngine.kt"

    index_text = index.read_text(encoding="utf-8")
    engine_text = engine.read_text(encoding="utf-8")

    assert 'assetFileName: String = "medical_qa_sample.jsonl"' in engine_text
    assert "context.assets.open(assetFileName)" in engine_text
    assert "fun search(query: String, topK: Int = 3)" in index_text
    assert "retrievalMs" in engine_text
    assert "generationMs" in engine_text
    assert "totalMs" in engine_text
    assert "SystemClock.elapsedRealtimeNanos()" in engine_text
    assert "DISCLAIMER" in engine_text
    assert "근거:" in engine_text
    assert "sanitizeAnswerText" in engine_text
    assert "CONTROL_TOKEN_PATTERN" in engine_text
    assert "MARKDOWN_MARKER_PATTERN" in engine_text
    assert "MARKDOWN_LIST_MARKER_PATTERN" in engine_text
    assert "INTERNAL_ID_PATTERN" in engine_text
    assert ".sanitizeAnswerText().withDisclaimer()" in engine_text
    assert "근거 ${idx + 1}" in engine_text
    assert "내부 ID" in engine_text
    assert "record.qaId" not in engine_text
    assert "hit.record.qaId" not in engine_text
    assert "qa_id" not in engine_text


def test_android_ui_presents_service_bootstrap_without_file_import() -> None:
    activity = ANDROID / "app" / "src" / "main" / "java" / "com" / "mededge" / "rag" / "MainActivity.kt"
    activity_text = activity.read_text(encoding="utf-8")

    assert "Intent.ACTION_OPEN_DOCUMENT" not in activity_text
    assert "startActivityForResult" not in activity_text
    assert "onActivityResult" not in activity_text
    assert "LocalModelStore.importFromUri" not in activity_text
    assert "ModelBootstrapper.isEnabled" in activity_text
    assert "ModelBootstrapper.download" in activity_text
    assert "MedEdge RAG" in activity_text
    assert "로컬 Gemma 4 의료 Q&A" in activity_text
    assert "모델 상태" in activity_text
    assert "Gemma4 모델 다운로드" in activity_text
    assert "downloadProgressText" in activity_text
    assert "다운로드 진행률" in activity_text
    assert "downloadProgressText.text = \"다운로드 $percent%\"" in activity_text
    assert "downloadButton.visibility = if (ModelBootstrapper.isEnabled && !LocalModelStore.hasModel(this)) View.VISIBLE else View.GONE" in activity_text
    assert "Gemma4 모델 다시 다운로드" not in activity_text
    assert "온디바이스 답변 생성" in activity_text
    assert "근거 ${idx + 1} · ${hit.record.domain} · ${hit.record.qType}" in activity_text
    assert "score=$score" in activity_text
    assert "${hit.record.qaId} | ${hit.record.domain}" not in activity_text
    assert "오프라인 검증 빌드" in activity_text
    assert "모델 파일을 가져오는 중입니다." not in activity_text
    assert "MEDEDGE_BOOTSTRAP_DOWNLOAD ready=true" in activity_text
    assert "intent.getBooleanExtra(EXTRA_BOOTSTRAP_DOWNLOAD_TEST, false)" in activity_text
    assert "override fun onNewIntent" in activity_text
    assert "handleAutomationIntent(intent)" in activity_text
    assert "MEDEDGE_RAG_SMOKE usedLocalModel=" in activity_text
    assert "intent.getBooleanExtra(EXTRA_SMOKE_TEST, false)" in activity_text
    assert "benchmark_test" in activity_text
    assert "benchmark_repeat" in activity_text
    assert "MEDEDGE_RAG_BENCHMARK " in activity_text
    assert "MEDEDGE_RAG_BENCHMARK_DONE" in activity_text
    assert "retrieval_ms" in activity_text
    assert "generation_ms" in activity_text
    assert "total_ms" in activity_text
    assert "JSONObject" in activity_text


def test_bootstrap_model_downloader_is_flavor_scoped_and_hash_verified() -> None:
    offline_bootstrapper = ANDROID / "app" / "src" / "offline" / "java" / "com" / "mededge" / "rag" / "ModelBootstrapper.kt"
    bootstrapper = ANDROID / "app" / "src" / "bootstrap" / "java" / "com" / "mededge" / "rag" / "ModelBootstrapper.kt"

    offline_text = offline_bootstrapper.read_text(encoding="utf-8")
    bootstrap_text = bootstrapper.read_text(encoding="utf-8")

    assert "const val isEnabled = false" in offline_text
    assert "HttpURLConnection" not in offline_text
    assert "const val isEnabled = true" in bootstrap_text
    assert "HttpURLConnection" in bootstrap_text
    assert "MessageDigest.getInstance(\"SHA-256\")" in bootstrap_text
    assert "MODEL_DOWNLOAD_URL" in bootstrap_text
    assert "MODEL_SHA256" in bootstrap_text
    assert ".download" in bootstrap_text
    assert "delete()" in bootstrap_text


def test_android_ondevice_check_script_covers_build_and_device_model() -> None:
    script = ROOT / "scripts" / "run_android_ondevice_check.ps1"
    script_text = script.read_text(encoding="utf-8")

    assert "android.permission.INTERNET" in script_text
    assert "offlineDebug" in script_text
    assert ":app:assembleOfflineDebug" in script_text
    assert "app-offline-debug.apk" in script_text
    assert "dump permissions" in script_text
    assert "adb shell" in script_text
    assert "LocalModelFile" in script_text
    assert "adb push" in script_text
    assert "chmod 755" in script_text
    assert "chmod 644" in script_text
    assert "gemma-4-E2B-it.litertlm" in script_text
    assert "adb install -r" in script_text
    assert "am start -n" in script_text
    assert "RunSmokeTest" in script_text
    assert "MEDEDGE_RAG_SMOKE usedLocalModel=true" in script_text
    assert "adb logcat" in script_text
    assert "pidof" in script_text
    assert "AndroidRuntime:E" in script_text
    assert "dumpsys activity exit-info" in script_text
    assert "APP CRASH(NATIVE)" in script_text
    assert "Assert-AppProcessRunning" in script_text
    assert "/data/local/tmp/llm/gemma-4-E2B-it.litertlm" in script_text
    assert "verify_android_apk.py" in script_text


def test_android_bootstrap_check_script_covers_download_and_local_smoke() -> None:
    script = ROOT / "scripts" / "run_android_bootstrap_check.ps1"
    script_text = script.read_text(encoding="utf-8")

    assert ":app:assembleBootstrapDebug" in script_text
    assert "app-bootstrap-debug.apk" in script_text
    assert "--allow-internet" in script_text
    assert "--require-internet" in script_text
    assert "ApkPermissionsText" in script_text
    assert "pm clear com.mededge.rag" in script_text
    assert "/data/local/tmp/llm/gemma-4-E2B-it.litertlm" in script_text
    assert "bootstrap_download_test" in script_text
    assert "MEDEDGE_BOOTSTRAP_DOWNLOAD ready=true" in script_text
    assert "am force-stop com.mededge.rag" in script_text
    assert "MEDEDGE_RAG_SMOKE usedLocalModel=true" in script_text


def test_android_resource_benchmark_script_collects_metrics() -> None:
    script = ROOT / "scripts" / "run_android_resource_benchmark.ps1"
    script_text = script.read_text(encoding="utf-8")

    assert ":app:assembleOfflineDebug" in script_text
    assert "app-offline-debug.apk" in script_text
    assert "verify_android_apk.py" in script_text
    assert "benchmark_test" in script_text
    assert "benchmark_repeat" in script_text
    assert "MEDEDGE_RAG_BENCHMARK" in script_text
    assert "MEDEDGE_RAG_BENCHMARK_DONE" in script_text
    assert "dumpsys meminfo" in script_text
    assert "top -b -n 1" in script_text
    assert "du -sk" in script_text
    assert "android_ondevice_metrics_raw.csv" in script_text
    assert "android_ondevice_metrics_summary.csv" in script_text
    assert "android_ondevice_metrics.md" in script_text
    assert "used_local_model" in script_text


def test_android_emulator_scripts_create_pixel7_and_run_smoke() -> None:
    create_script = ROOT / "scripts" / "create_android_emulator.ps1"
    run_script = ROOT / "scripts" / "run_android_emulator_check.ps1"

    create_text = create_script.read_text(encoding="utf-8")
    run_text = run_script.read_text(encoding="utf-8")

    assert "MedEdge_Pixel_7_API_35" in create_text
    assert "pixel_7" in create_text
    assert "system-images;android-35;google_apis;x86_64" in create_text
    assert "disk.dataPartition.size" in create_text
    assert "hw.ramSize" in create_text
    assert "sdkmanager" in create_text
    assert "avdmanager" in create_text
    assert "MedEdge_Pixel_7_API_35" in run_text
    assert "emulator.exe" in run_text
    assert "getprop sys.boot_completed" in run_text
    assert "run_android_ondevice_check.ps1" in run_text
    assert "SmokeTimeoutSeconds" in run_text
    assert "-InstallApk" in run_text
    assert "-RunSmokeTest" in run_text


def test_android_project_has_gradle_wrapper() -> None:
    wrapper = ANDROID / "gradlew.bat"
    properties = ANDROID / "gradle" / "wrapper" / "gradle-wrapper.properties"

    assert wrapper.is_file()
    assert "gradle-8.10.2-bin.zip" in properties.read_text(encoding="utf-8")


def test_android_source_has_no_network_client_or_cloud_endpoint() -> None:
    forbidden = [
        "HttpURLConnection",
        "java.net.",
        "okhttp",
        "retrofit",
        "https://",
        "http://",
        "OLLAMA_HOST",
        "OLLAMA_API_KEY",
        "Gemini API",
    ]

    source_roots = [
        ANDROID / "app" / "src" / "main" / "java",
        ANDROID / "app" / "src" / "offline" / "java",
    ]
    for path in [p for root in source_roots for p in root.rglob("*.kt")]:
        text = path.read_text(encoding="utf-8")
        for pattern in forbidden:
            assert pattern not in text, f"{pattern!r} found in {path}"


def test_android_apk_verifier_checks_assets_runtime_and_forbidden_artifacts() -> None:
    verifier = ROOT / "scripts" / "verify_android_apk.py"
    verifier_text = verifier.read_text(encoding="utf-8")

    assert "assets/medical_qa_sample.jsonl" in verifier_text
    assert "lib/arm64-v8a/" in verifier_text
    assert "lib/x86_64/" in verifier_text
    assert "litert" in verifier_text
    assert "android.permission.INTERNET" in verifier_text
    assert "--allow-internet" in verifier_text
    assert "--require-internet" in verifier_text
    assert '".task"' in verifier_text
    assert '".litertlm"' in verifier_text
    assert '"pytorch_model.bin"' in verifier_text
    assert "data/raw/" in verifier_text


def test_android_docs_pin_gemma4_source_model_and_task_runtime() -> None:
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    android_readme_text = (ANDROID / "README.md").read_text(encoding="utf-8")

    assert "google/gemma-4-E2B-it" in readme_text
    assert "google/gemma-4-E2B-it" in android_readme_text
    assert "litert-community/gemma-4-E2B-it-litert-lm" in readme_text
    assert "litert-community/gemma-4-E2B-it-litert-lm" in android_readme_text
    assert "LiteRT-LM" in readme_text
    assert "LiteRT-LM" in android_readme_text
    assert "MediaPipe LLM Inference" not in readme_text
    assert "MediaPipe LLM Inference" not in android_readme_text
    assert "MedEdge_Pixel_7_API_35" in readme_text
    assert "MedEdge_Pixel_7_API_35" in android_readme_text
    assert "pixel_7" in readme_text
    assert "pixel_7" in android_readme_text
    assert ".litertlm" in readme_text
    assert ".litertlm" in android_readme_text
    assert "offline" in readme_text
    assert "bootstrap" in readme_text
    assert "offline" in android_readme_text
    assert "bootstrap" in android_readme_text


def test_gemma4_download_script_keeps_model_out_of_git() -> None:
    script = ROOT / "scripts" / "download_gemma4_litert_model.ps1"
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    script_text = script.read_text(encoding="utf-8")

    assert "litert-community/gemma-4-E2B-it-litert-lm" in script_text
    assert "gemma-4-E2B-it.litertlm" in script_text
    assert "Get-FileHash -Algorithm SHA256" in script_text
    assert "IsNullOrWhiteSpace($Sha256)" in script_text
    assert "data/**" in gitignore
    assert "models/*" in gitignore
    assert "android/**/src/main/assets/*.jsonl" in gitignore
