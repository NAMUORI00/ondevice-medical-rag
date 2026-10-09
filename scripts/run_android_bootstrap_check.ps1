param(
    [string]$ProjectDir = "android\MedEdgeRag",
    [string]$PackageName = "com.mededge.rag",
    [switch]$InstallApk,
    [switch]$RunDownloadTest,
    [int]$DownloadTimeoutSeconds = 900,
    [int]$SmokeTimeoutSeconds = 600
)

$ErrorActionPreference = "Stop"
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$AndroidProject = Resolve-Path (Join-Path $Root $ProjectDir)
$ActivityName = "$PackageName/.MainActivity"
$ModelPath = "/data/local/tmp/llm/gemma-4-E2B-it.litertlm"

function Assert-NoAndroidRuntimeCrash {
    $CrashOutput = & adb logcat -d -s "AndroidRuntime:E" 2>$null
    if ($CrashOutput -match $PackageName) {
        throw "Android app crashed: $CrashOutput"
    }
}

function Assert-AppProcessRunning {
    Start-Sleep -Seconds 2
    $ProcessId = & adb shell pidof $PackageName 2>$null
    if ([string]::IsNullOrWhiteSpace($ProcessId)) {
        Assert-NoAndroidRuntimeCrash
        throw "Android app process is not running: $PackageName"
    }
}

if (-not (Get-Command java -ErrorAction SilentlyContinue)) {
    throw "JDK is required for Android build verification, but java is not on PATH."
}
if (-not (Get-Command adb -ErrorAction SilentlyContinue)) {
    throw "adb is required for bootstrap device verification."
}

$GradleWrapper = Join-Path $AndroidProject "gradlew.bat"
if (-not (Test-Path $GradleWrapper)) {
    throw "android\MedEdgeRag\gradlew.bat is required for Android build verification."
}

Push-Location $AndroidProject
try {
    & $GradleWrapper "--no-daemon" ":app:assembleBootstrapDebug"
    if ($LASTEXITCODE -ne 0) {
        throw "Android bootstrap Gradle build failed."
    }
} finally {
    Pop-Location
}

$Apk = Join-Path $AndroidProject "app\build\outputs\apk\bootstrap\debug\app-bootstrap-debug.apk"
if (-not (Test-Path $Apk)) {
    throw "Bootstrap debug APK was not produced: $Apk"
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
    throw "Failed to inspect bootstrap APK permissions."
}
$ApkPermissionsText = $ApkPermissions -join "`n"
if ($ApkPermissionsText -notmatch "android.permission.INTERNET") {
    throw "Bootstrap APK must declare INTERNET permission."
}

python (Join-Path $Root "scripts\verify_android_apk.py") --apk $Apk --aapt $Aapt.FullName --allow-internet --require-internet
if ($LASTEXITCODE -ne 0) {
    throw "Android bootstrap APK verification failed."
}

if (-not $InstallApk -and -not $RunDownloadTest) {
    Write-Host "Android bootstrap APK check passed."
    return
}

$PreviousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$DeviceState = & adb get-state 2>$null
$AdbExitCode = $LASTEXITCODE
$ErrorActionPreference = $PreviousErrorActionPreference
if ($AdbExitCode -ne 0 -or $DeviceState.Trim() -ne "device") {
    throw "No Android device is connected through adb."
}

& adb install -r $Apk
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install bootstrap debug APK on the connected Android device."
}

if ($RunDownloadTest) {
    & adb shell "rm -f '$ModelPath'"
    & adb shell pm clear com.mededge.rag
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to clear app data before bootstrap download test."
    }

    & adb shell am force-stop com.mededge.rag
    & adb shell am force-stop com.mededge.rag
    & adb logcat -c
    & adb shell am start -n $ActivityName --ez bootstrap_download_test true
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to launch bootstrap download test."
    }
    Assert-AppProcessRunning

    $Deadline = (Get-Date).AddSeconds($DownloadTimeoutSeconds)
    while ((Get-Date) -lt $Deadline) {
        $LogOutput = & adb logcat -d -s "MedEdgeRag:I" 2>$null
        Assert-NoAndroidRuntimeCrash
        if ($LogOutput -match "MEDEDGE_BOOTSTRAP_DOWNLOAD ready=true") {
            Write-Host "Android bootstrap Gemma4 download test passed."
            break
        }
        if ($LogOutput -match "MEDEDGE_BOOTSTRAP_DOWNLOAD failed=") {
            throw "Android bootstrap Gemma4 download test failed: $LogOutput"
        }
        Start-Sleep -Seconds 2
    }
    if ((Get-Date) -ge $Deadline) {
        throw "Timed out waiting for Android bootstrap Gemma4 download test."
    }

    & adb logcat -c
    & adb shell am start -n $ActivityName --ez smoke_test true
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to launch post-download Gemma4 smoke test."
    }
    Assert-AppProcessRunning

    $SmokeDeadline = (Get-Date).AddSeconds($SmokeTimeoutSeconds)
    while ((Get-Date) -lt $SmokeDeadline) {
        $LogOutput = & adb logcat -d -s "MedEdgeRag:I" 2>$null
        Assert-NoAndroidRuntimeCrash
        if ($LogOutput -match "MEDEDGE_RAG_SMOKE usedLocalModel=true") {
            Write-Host "Android bootstrap post-download Gemma4 smoke test passed."
            break
        }
        if ($LogOutput -match "MEDEDGE_RAG_SMOKE failed=" -or $LogOutput -match "usedLocalModel=false") {
            throw "Android bootstrap post-download Gemma4 smoke test failed: $LogOutput"
        }
        Start-Sleep -Seconds 2
    }
    if ((Get-Date) -ge $SmokeDeadline) {
        throw "Timed out waiting for Android bootstrap post-download Gemma4 smoke test."
    }
}

Write-Host "Android bootstrap check passed."
