param(
    [string]$ProjectDir = "android\MedEdgeRag",
    [string]$BuildVariant = "offlineDebug",
    [string]$BuildTask = ":app:assembleOfflineDebug",
    [string]$ModelPath = "/data/local/tmp/llm/gemma-4-E2B-it.litertlm",
    [string]$LocalModelFile = "",
    [switch]$InstallApk,
    [switch]$LaunchApp,
    [switch]$RunSmokeTest,
    [int]$SmokeTimeoutSeconds = 120
)

$ErrorActionPreference = "Stop"
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$AndroidProject = Resolve-Path (Join-Path $Root $ProjectDir)
$Manifest = Join-Path $AndroidProject "app\src\main\AndroidManifest.xml"
$PackageName = "com.mededge.rag"
$ActivityName = "$PackageName/.MainActivity"
$NativeCrashMarker = "APP CRASH(NATIVE)"

function Assert-NoAndroidRuntimeCrash {
    param([switch]$IncludeExitInfo)

    $CrashOutput = & adb logcat -d -s "AndroidRuntime:E" 2>$null
    if ($CrashOutput -match $PackageName) {
        throw "Android app crashed: $CrashOutput"
    }
    if ($IncludeExitInfo) {
        $ExitInfo = & adb shell dumpsys activity exit-info $PackageName 2>$null
        if ($ExitInfo -match [regex]::Escape($NativeCrashMarker)) {
            throw "Android app native crash: $ExitInfo"
        }
        $NativeCrashOutput = & adb logcat -d -v time 2>$null | Select-String -Pattern "Fatal signal|F native|$PackageName" -Context 2,4
        if ($NativeCrashOutput -match "Fatal signal|F native") {
            throw "Android app native crash: $NativeCrashOutput"
        }
    }
}

function Assert-AppProcessRunning {
    Start-Sleep -Seconds 2
    $ProcessId = & adb shell pidof $PackageName 2>$null
    if ([string]::IsNullOrWhiteSpace($ProcessId)) {
        Assert-NoAndroidRuntimeCrash -IncludeExitInfo
        throw "Android app process is not running: $PackageName"
    }
}

if ((Get-Content $Manifest -Raw) -match "android.permission.INTERNET") {
    throw "Android manifest declares INTERNET permission. This demo must remain fully on-device."
}

if (-not (Get-Command java -ErrorAction SilentlyContinue)) {
    throw "JDK is required for Android build verification, but java is not on PATH."
}

$GradleCommand = Get-Command gradle -ErrorAction SilentlyContinue
$GradleWrapper = Join-Path $AndroidProject "gradlew.bat"
if (Test-Path $GradleWrapper) {
    $GradleExecutable = $GradleWrapper
} elseif ($GradleCommand) {
    $GradleExecutable = $GradleCommand.Source
} else {
    throw "Gradle or android\MedEdgeRag\gradlew.bat is required for Android build verification."
}

if (-not (Get-Command adb -ErrorAction SilentlyContinue)) {
    throw "adb is required to verify the on-device Gemma4 model file."
}

Push-Location $AndroidProject
try {
    & $GradleExecutable "--no-daemon" $BuildTask
    if ($LASTEXITCODE -ne 0) {
        throw "Android Gradle build failed."
    }
} finally {
    Pop-Location
}

$Apk = Join-Path $AndroidProject "app\build\outputs\apk\offline\debug\app-offline-debug.apk"
if (-not (Test-Path $Apk)) {
    throw "Debug APK was not produced: $Apk"
}

$SdkRoot = $env:ANDROID_HOME
if ([string]::IsNullOrWhiteSpace($SdkRoot)) {
    $SdkRoot = $env:ANDROID_SDK_ROOT
}
if ([string]::IsNullOrWhiteSpace($SdkRoot)) {
    $AdbPath = (Get-Command adb).Source
    $SdkRoot = Split-Path (Split-Path $AdbPath -Parent) -Parent
}

$Aapt = Get-ChildItem (Join-Path $SdkRoot "build-tools") -Recurse -Filter "aapt.exe" -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending |
    Select-Object -First 1
if (-not $Aapt) {
    throw "aapt.exe was not found under Android SDK build-tools."
}

$ApkPermissions = & $Aapt.FullName dump permissions $Apk
if ($LASTEXITCODE -ne 0) {
    throw "Failed to inspect APK permissions."
}
if ($ApkPermissions -match "android.permission.INTERNET") {
    throw "Built APK declares INTERNET permission. This demo must remain fully on-device."
}

python (Join-Path $Root "scripts\verify_android_apk.py") --apk $Apk --aapt $Aapt.FullName
if ($LASTEXITCODE -ne 0) {
    throw "Android APK verification failed."
}

$PreviousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$DeviceState = & adb get-state 2>$null
$AdbExitCode = $LASTEXITCODE
$ErrorActionPreference = $PreviousErrorActionPreference
if ($AdbExitCode -ne 0 -or $DeviceState.Trim() -ne "device") {
    throw "No Android device is connected through adb."
}

if (-not [string]::IsNullOrWhiteSpace($LocalModelFile)) {
    $ResolvedModelFile = Resolve-Path $LocalModelFile
    $RemoteModelDir = $ModelPath -replace "/[^/]+$", ""
    & adb shell "mkdir -p '$RemoteModelDir'"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create remote model directory: $RemoteModelDir"
    }
    & adb shell "chmod 755 '$RemoteModelDir'"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to make remote model directory readable: $RemoteModelDir"
    }

    & adb push $ResolvedModelFile.Path $ModelPath
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to push local Gemma4 model to device: $ModelPath"
    }
    & adb shell "chmod 644 '$ModelPath'"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to make remote Gemma4 model file readable: $ModelPath"
    }
}

if ($InstallApk) {
    & adb install -r $Apk
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install debug APK on the connected Android device."
    }
}

$PreviousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& adb shell "test -f '$ModelPath'"
$ModelExitCode = $LASTEXITCODE
$ErrorActionPreference = $PreviousErrorActionPreference
if ($ModelExitCode -ne 0) {
    throw "Gemma4 model file is missing on device: $ModelPath"
}

if ($LaunchApp) {
    & adb logcat -c
    & adb shell am start -n $ActivityName
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to launch MedEdge RAG on the connected Android device."
    }
    Assert-AppProcessRunning
    Assert-NoAndroidRuntimeCrash
}

if ($RunSmokeTest) {
    & adb logcat -c
    & adb shell am start -n $ActivityName --ez smoke_test true
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to launch MedEdge RAG smoke test."
    }
    Assert-AppProcessRunning

    $Deadline = (Get-Date).AddSeconds($SmokeTimeoutSeconds)
    while ((Get-Date) -lt $Deadline) {
        $LogOutput = & adb logcat -d -s "MedEdgeRag:I" 2>$null
        Assert-NoAndroidRuntimeCrash
        if ($LogOutput -match "MEDEDGE_RAG_SMOKE usedLocalModel=true") {
            Write-Host "Android on-device Gemma4 smoke test passed."
            break
        }
        if ($LogOutput -match "MEDEDGE_RAG_SMOKE failed=" -or $LogOutput -match "usedLocalModel=false") {
            throw "Android on-device Gemma4 smoke test failed: $LogOutput"
        }
        Start-Sleep -Seconds 2
    }

    if ((Get-Date) -ge $Deadline) {
        throw "Timed out waiting for Android on-device Gemma4 smoke test."
    }
}

Write-Host "Android on-device check passed."
