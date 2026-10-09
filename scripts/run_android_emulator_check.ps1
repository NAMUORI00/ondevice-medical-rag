param(
    [string]$AvdName = "MedEdge_Pixel_7_API_35",
    [string]$LocalModelFile = "models\gemma-4-E2B-it.litertlm",
    [int]$BootTimeoutSeconds = 360,
    [int]$SmokeTimeoutSeconds = 600,
    [switch]$CreateAvd,
    [switch]$ShutdownWhenDone
)

$ErrorActionPreference = "Stop"
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")

function Require-Command {
    param([string]$Name)

    $Command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $Command) {
        throw "$Name is required on PATH."
    }
    return $Command
}

function Resolve-InputPath {
    param([string]$Path)

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return Resolve-Path $Path
    }
    return Resolve-Path (Join-Path $Root $Path)
}

function Get-FirstEmulatorSerial {
    $Lines = & adb devices
    foreach ($Line in $Lines) {
        if ($Line -match "^(emulator-\d+)\s+device$") {
            return $Matches[1]
        }
    }
    return $null
}

if ($CreateAvd) {
    & (Join-Path $PSScriptRoot "create_android_emulator.ps1") -AvdName $AvdName
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create Android emulator AVD: $AvdName"
    }
}

$ModelCandidate = $LocalModelFile
if (-not [System.IO.Path]::IsPathRooted($ModelCandidate)) {
    $ModelCandidate = Join-Path $Root $ModelCandidate
}
if (-not (Test-Path $ModelCandidate)) {
    throw "Gemma4 LiteRT model file not found: $LocalModelFile. Run scripts\download_gemma4_litert_model.ps1 first, or pass -LocalModelFile."
}
$ResolvedModelFile = Resolve-InputPath $LocalModelFile

$Emulator = Require-Command "emulator.exe"
$Adb = Require-Command "adb"
$StartedProcess = $null

if (-not (Get-FirstEmulatorSerial)) {
    $EmulatorArgs = @(
        "-avd", $AvdName,
        "-no-snapshot-load",
        "-no-audio",
        "-no-boot-anim",
        "-gpu", "swiftshader_indirect",
        "-no-window"
    )
    $StartedProcess = Start-Process -FilePath $Emulator.Source -ArgumentList $EmulatorArgs -PassThru -WindowStyle Hidden
}

try {
    & $Adb.Source wait-for-device
    if ($LASTEXITCODE -ne 0) {
        throw "adb did not detect the Android emulator."
    }

    $Deadline = (Get-Date).AddSeconds($BootTimeoutSeconds)
    $Serial = $null
    while ((Get-Date) -lt $Deadline) {
        $Serial = Get-FirstEmulatorSerial
        if (-not [string]::IsNullOrWhiteSpace($Serial)) {
            $BootCompleted = (& $Adb.Source -s $Serial shell "getprop sys.boot_completed" 2>$null).Trim()
            if ($BootCompleted -eq "1") {
                break
            }
        }
        Start-Sleep -Seconds 2
    }

    if ([string]::IsNullOrWhiteSpace($Serial)) {
        throw "Android emulator did not appear in adb devices."
    }

    $BootCompleted = (& $Adb.Source -s $Serial shell "getprop sys.boot_completed" 2>$null).Trim()
    if ($BootCompleted -ne "1") {
        throw "Timed out waiting for Android emulator boot: $AvdName"
    }

    & $Adb.Source -s $Serial shell input keyevent 82 | Out-Null

    $PreviousSerial = $env:ANDROID_SERIAL
    $env:ANDROID_SERIAL = $Serial
    try {
        & (Join-Path $PSScriptRoot "run_android_ondevice_check.ps1") -LocalModelFile $ResolvedModelFile.Path -InstallApk -RunSmokeTest -SmokeTimeoutSeconds $SmokeTimeoutSeconds
        if ($LASTEXITCODE -ne 0) {
            throw "Android emulator on-device check failed."
        }
    } finally {
        $env:ANDROID_SERIAL = $PreviousSerial
    }
} finally {
    if ($ShutdownWhenDone) {
        $Serial = Get-FirstEmulatorSerial
        if (-not [string]::IsNullOrWhiteSpace($Serial)) {
            & $Adb.Source -s $Serial emu kill | Out-Null
        } elseif ($StartedProcess -and -not $StartedProcess.HasExited) {
            $StartedProcess.Kill()
        }
    }
}

Write-Host "Android emulator Gemma4 smoke check passed: $AvdName"
