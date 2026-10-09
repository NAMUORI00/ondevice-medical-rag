param(
    [string]$ProjectDir = "android\MedEdgeRag",
    [string]$LocalModelFile = "models\gemma-4-E2B-it.litertlm",
    [string]$ModelPath = "/data/local/tmp/llm/gemma-4-E2B-it.litertlm",
    [string]$DeviceSerial = "",
    [int]$Repeats = 1,
    [int]$TimeoutSeconds = 900,
    [string]$OutputDir = "experiments"
)

$ErrorActionPreference = "Stop"
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$AndroidProject = Resolve-Path (Join-Path $Root $ProjectDir)
$PackageName = "com.mededge.rag"
$ActivityName = "$PackageName/.MainActivity"
$BuildTask = ":app:assembleOfflineDebug"
$Apk = Join-Path $AndroidProject "app\build\outputs\apk\offline\debug\app-offline-debug.apk"
$ExpectedQuestions = 3
$ExpectedCount = $Repeats * $ExpectedQuestions

function Require-Command {
    param([string]$Name)
    $Command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $Command) {
        throw "$Name is required on PATH."
    }
    return $Command.Source
}

function First-DeviceSerial {
    $Devices = (& adb devices) -join "`n"
    foreach ($Line in ($Devices -split "`n")) {
        if ($Line -match "^(\S+)\s+device$") {
            return $Matches[1]
        }
    }
    throw "No Android device or emulator is connected."
}

function Parse-Kb {
    param([string]$Value)
    return [int64]($Value -replace ",", "")
}

function Get-PssKb {
    $Output = (& adb -s $DeviceSerial shell dumpsys meminfo $PackageName 2>$null) -join "`n"
    if ($Output -match "TOTAL PSS:\s*([0-9,]+)") {
        return Parse-Kb $Matches[1]
    }
    foreach ($Line in ($Output -split "`n")) {
        if ($Line -match "^\s*TOTAL\s+([0-9,]+)\s+") {
            return Parse-Kb $Matches[1]
        }
    }
    return 0
}

function Get-CpuPercent {
    $Output = (& adb -s $DeviceSerial shell top -b -n 1 2>$null) -join "`n"
    $Line = ($Output -split "`n" | Where-Object { $_ -match [regex]::Escape($PackageName) } | Select-Object -First 1)
    if ($Line -and $Line -match "([0-9]+(?:\.[0-9]+)?)%") {
        return [double]$Matches[1]
    }
    if ($Line) {
        $Parts = $Line.Trim() -split "\s+"
        for ($Index = 0; $Index -lt ($Parts.Count - 1); $Index++) {
            if ($Parts[$Index] -match "^[RSDZT]$" -and $Parts[$Index + 1] -match "^[0-9]+(?:\.[0-9]+)?$") {
                return [double]$Parts[$Index + 1]
            }
        }
    }
    return $null
}

function Get-DuKb {
    param([string]$Path)
    $Output = (& adb -s $DeviceSerial shell du -sk $Path 2>$null) -join "`n"
    if ($Output -match "^\s*([0-9]+)") {
        return [int64]$Matches[1]
    }
    return 0
}

function Get-AppFilesKb {
    $Output = (& adb -s $DeviceSerial shell run-as $PackageName du -sk files 2>$null) -join "`n"
    if ($Output -match "^\s*([0-9]+)") {
        return [int64]$Matches[1]
    }
    return 0
}

function Average {
    param([double[]]$Values)
    if (-not $Values -or $Values.Count -eq 0) {
        return 0
    }
    return [math]::Round(($Values | Measure-Object -Average).Average, 2)
}

function StdDev {
    param([double[]]$Values)
    if (-not $Values -or $Values.Count -le 1) {
        return 0
    }
    $Avg = ($Values | Measure-Object -Average).Average
    $Variance = ($Values | ForEach-Object { [math]::Pow($_ - $Avg, 2) } | Measure-Object -Average).Average
    return [math]::Round([math]::Sqrt($Variance), 2)
}

Require-Command "adb" | Out-Null
Require-Command "java" | Out-Null
Require-Command "python" | Out-Null

if ([string]::IsNullOrWhiteSpace($DeviceSerial)) {
    $DeviceSerial = First-DeviceSerial
}

$GradleWrapper = Join-Path $AndroidProject "gradlew.bat"
if (Test-Path $GradleWrapper) {
    $GradleExecutable = $GradleWrapper
} else {
    $GradleExecutable = Require-Command "gradle"
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

& python (Join-Path $Root "scripts\verify_android_apk.py") --apk $Apk
if ($LASTEXITCODE -ne 0) {
    throw "Android APK verification failed."
}

if (-not (Test-Path $LocalModelFile)) {
    throw "Local model file was not found: $LocalModelFile"
}

$ResolvedModel = Resolve-Path $LocalModelFile
& adb -s $DeviceSerial install -r $Apk
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install APK."
}

& adb -s $DeviceSerial shell pm clear $PackageName | Out-Null
& adb -s $DeviceSerial shell mkdir -p (Split-Path -Parent $ModelPath).Replace("\", "/") | Out-Null
& adb -s $DeviceSerial push $ResolvedModel $ModelPath
if ($LASTEXITCODE -ne 0) {
    throw "Failed to push model to device."
}
& adb -s $DeviceSerial shell chmod 755 (Split-Path -Parent $ModelPath).Replace("\", "/") | Out-Null
& adb -s $DeviceSerial shell chmod 644 $ModelPath | Out-Null

$DeviceModel = ((& adb -s $DeviceSerial shell getprop ro.product.model) -join "").Trim()
$ApiLevel = ((& adb -s $DeviceSerial shell getprop ro.build.version.sdk) -join "").Trim()
$ApkMiB = [math]::Round((Get-Item $Apk).Length / 1MB, 2)
$ModelGiB = [math]::Round((Get-Item $ResolvedModel).Length / 1GB, 3)

& adb -s $DeviceSerial logcat -c
& adb -s $DeviceSerial shell am force-stop $PackageName | Out-Null
& adb -s $DeviceSerial shell am start -n $ActivityName --ez benchmark_test true --ei benchmark_repeat $Repeats | Out-Null

$PeakPssKb = 0
$CpuSamples = @()
$LogOutput = ""
$Deadline = (Get-Date).AddSeconds($TimeoutSeconds)

do {
    Start-Sleep -Seconds 3
    $PssKb = Get-PssKb
    if ($PssKb -gt $PeakPssKb) {
        $PeakPssKb = $PssKb
    }
    $Cpu = Get-CpuPercent
    if ($null -ne $Cpu) {
        $CpuSamples += $Cpu
    }
    $LogOutput = (& adb -s $DeviceSerial logcat -d -s "MedEdgeRag:I") -join "`n"
    if ($LogOutput -match "MEDEDGE_RAG_BENCHMARK_DONE count=$ExpectedCount") {
        break
    }
    if ($LogOutput -match "MEDEDGE_RAG_BENCHMARK\s+\{[^`n]*`"error`"") {
        throw "Benchmark app error: $LogOutput"
    }
} while ((Get-Date) -lt $Deadline)

if ($LogOutput -notmatch "MEDEDGE_RAG_BENCHMARK_DONE count=$ExpectedCount") {
    throw "Timed out waiting for MEDEDGE_RAG_BENCHMARK_DONE count=$ExpectedCount. Log: $LogOutput"
}

$Rows = @()
foreach ($Line in ($LogOutput -split "`n")) {
    if ($Line -match "MEDEDGE_RAG_BENCHMARK\s+(\{.*\})") {
        $Json = $Matches[1] | ConvertFrom-Json
        if ($Json.PSObject.Properties.Name -contains "error") {
            throw "Benchmark row failed: $($Matches[1])"
        }
        $Rows += [pscustomobject]@{
            device = $DeviceModel
            api_level = $ApiLevel
            build = "offlineDebug"
            seq = [int]$Json.seq
            round = [int]$Json.round
            question_index = [int]$Json.question_index
            question = [string]$Json.question
            used_local_model = [bool]$Json.used_local_model
            evidence = [int]$Json.evidence
            retrieval_ms = [int64]$Json.retrieval_ms
            generation_ms = [int64]$Json.generation_ms
            total_ms = [int64]$Json.total_ms
        }
    }
}

$Rows = $Rows | Group-Object seq | ForEach-Object { $_.Group[-1] } | Sort-Object seq
if ($Rows.Count -ne $ExpectedCount) {
    throw "Expected $ExpectedCount benchmark rows but parsed $($Rows.Count)."
}

$Out = Resolve-Path $Root
$OutputPath = Join-Path $Out $OutputDir
New-Item -ItemType Directory -Force -Path $OutputPath | Out-Null

$RawCsv = Join-Path $OutputPath "android_ondevice_metrics_raw.csv"
$SummaryCsv = Join-Path $OutputPath "android_ondevice_metrics_summary.csv"
$Markdown = Join-Path $OutputPath "android_ondevice_metrics.md"

$Rows | Export-Csv -NoTypeInformation -Encoding UTF8 $RawCsv

$TotalMs = [double[]]($Rows | ForEach-Object { [double]$_.total_ms })
$RetrievalMs = [double[]]($Rows | ForEach-Object { [double]$_.retrieval_ms })
$GenerationMs = [double[]]($Rows | ForEach-Object { [double]$_.generation_ms })
$Evidence = [double[]]($Rows | ForEach-Object { [double]$_.evidence })
$UsedLocalModelAll = (($Rows | Where-Object { -not $_.used_local_model }).Count -eq 0)
$PeakPssMb = [math]::Round($PeakPssKb / 1024, 2)
$AvgCpu = Average ([double[]]$CpuSamples)
$PeakCpu = if ($CpuSamples.Count -gt 0) { [math]::Round(($CpuSamples | Measure-Object -Maximum).Maximum, 2) } else { 0 }
$ModelStorageKb = Get-DuKb $ModelPath
$AppFilesKb = Get-AppFilesKb

$Summary = [pscustomobject]@{
    device = $DeviceModel
    api_level = $ApiLevel
    build = "offlineDebug"
    repeats = $Repeats
    query_count = $Rows.Count
    total_ms_mean = Average $TotalMs
    total_ms_std = StdDev $TotalMs
    retrieval_ms_mean = Average $RetrievalMs
    generation_ms_mean = Average $GenerationMs
    evidence_mean = Average $Evidence
    used_local_model_all = $UsedLocalModelAll
    peak_pss_mb = $PeakPssMb
    cpu_percent_mean = $AvgCpu
    cpu_percent_peak = $PeakCpu
    apk_mib = $ApkMiB
    model_gib = $ModelGiB
    device_model_storage_kb = $ModelStorageKb
    app_files_storage_kb = $AppFilesKb
    internet_permission = "No INTERNET permission"
    raw_csv = $RawCsv
}

$Summary | Export-Csv -NoTypeInformation -Encoding UTF8 $SummaryCsv

@"
# Android On-device Metrics

| Device | Build | Queries | Total latency mean +/- std (ms) | Retrieval mean (ms) | Generation mean (ms) | Peak PSS (MB) | CPU mean / peak (%) | used_local_model |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| $DeviceModel API $ApiLevel | offlineDebug | $($Rows.Count) | $($Summary.total_ms_mean) +/- $($Summary.total_ms_std) | $($Summary.retrieval_ms_mean) | $($Summary.generation_ms_mean) | $($Summary.peak_pss_mb) | $($Summary.cpu_percent_mean) / $($Summary.cpu_percent_peak) | $($Summary.used_local_model_all) |

| APK MiB | Model GiB | Device model storage KB | App files storage KB | Network permission |
| ---: | ---: | ---: | ---: | --- |
| $($Summary.apk_mib) | $($Summary.model_gib) | $($Summary.device_model_storage_kb) | $($Summary.app_files_storage_kb) | $($Summary.internet_permission) |

- Raw CSV: ``$RawCsv``
- Summary CSV: ``$SummaryCsv``
"@ | Set-Content -Encoding UTF8 $Markdown

Write-Host "Android resource benchmark passed."
Write-Host "Raw CSV: $RawCsv"
Write-Host "Summary CSV: $SummaryCsv"
Write-Host "Markdown: $Markdown"
Write-Host ($Summary | ConvertTo-Json -Compress)
