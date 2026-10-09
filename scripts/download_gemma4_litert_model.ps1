param(
    [string]$Output = "models\gemma-4-E2B-it.litertlm",
    [string]$Url = "https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/b4f4f4df93418ddb4aa7da8bf33b584602a5b9f8/gemma-4-E2B-it.litertlm",
    [string]$Sha256 = "181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c"
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$OutputPath = Join-Path $Root $Output
$OutputDir = Split-Path $OutputPath -Parent

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

if (-not (Test-Path $OutputPath)) {
    if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
        & curl.exe -L --fail --output $OutputPath $Url
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to download Gemma4 LiteRT model from $Url"
        }
    } else {
        Invoke-WebRequest -Uri $Url -OutFile $OutputPath
    }
}

if (-not [string]::IsNullOrWhiteSpace($Sha256)) {
    $ActualHash = (Get-FileHash -Algorithm SHA256 $OutputPath).Hash.ToLowerInvariant()
    if ($ActualHash -ne $Sha256.ToLowerInvariant()) {
        throw "Gemma4 LiteRT model checksum mismatch. Expected $Sha256 but got $ActualHash"
    }
} else {
    Write-Warning "No SHA256 checksum was provided. Verify the model file against the source before publishing results."
}

Write-Host "Gemma4 LiteRT model ready: $OutputPath"
