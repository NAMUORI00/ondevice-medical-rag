param(
    [string]$AvdName = "MedEdge_Pixel_7_API_35",
    [string]$Device = "pixel_7",
    [string]$SystemImage = "system-images;android-35;google_apis;x86_64",
    [string]$DataPartitionSize = "8G",
    [string]$RamSize = "8192",
    [string]$VmHeapSize = "512M",
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

function Require-Command {
    param([string]$Name)

    $Command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $Command) {
        throw "$Name is required on PATH. Install Android Studio command-line tools and set ANDROID_HOME."
    }
    return $Command
}

function Set-AvdConfigValue {
    param(
        [string]$ConfigPath,
        [string]$Key,
        [string]$Value
    )

    $Lines = @()
    if (Test-Path $ConfigPath) {
        $Lines = Get-Content $ConfigPath
    }

    $Replacement = "$Key=$Value"
    $Updated = $false
    $NewLines = foreach ($Line in $Lines) {
        if ($Line -match "^$([regex]::Escape($Key))=") {
            $Updated = $true
            $Replacement
        } else {
            $Line
        }
    }

    if (-not $Updated) {
        $NewLines += $Replacement
    }
    Set-Content -Path $ConfigPath -Value $NewLines -Encoding ascii
}

$SdkManager = Require-Command "sdkmanager"
$AvdManager = Require-Command "avdmanager"
Require-Command "java" | Out-Null

if (-not $SkipInstall) {
    & $SdkManager.Source "emulator" $SystemImage
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install Android emulator package or system image: $SystemImage"
    }
}

$ExistingAvds = & $AvdManager.Source list avd
if ($ExistingAvds -match "Name:\s+$([regex]::Escape($AvdName))(\r?\n|$)") {
    Write-Host "Android emulator AVD already exists: $AvdName"
} else {
    "no" | & $AvdManager.Source create avd -n $AvdName -k $SystemImage -d $Device --force
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create Android emulator AVD: $AvdName"
    }
}

$ConfigPath = Join-Path $env:USERPROFILE ".android\avd\$AvdName.avd\config.ini"
if (-not (Test-Path $ConfigPath)) {
    throw "Android emulator config was not found: $ConfigPath"
}
Set-AvdConfigValue -ConfigPath $ConfigPath -Key "disk.dataPartition.size" -Value $DataPartitionSize
Set-AvdConfigValue -ConfigPath $ConfigPath -Key "hw.ramSize" -Value $RamSize
Set-AvdConfigValue -ConfigPath $ConfigPath -Key "vm.heapSize" -Value $VmHeapSize

Write-Host "Android emulator AVD ready: $AvdName ($Device, $SystemImage)"
