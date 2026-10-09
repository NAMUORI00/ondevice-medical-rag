param(
  [string]$IndexPath = "data/index/mededge_index.json",
  [string]$QueriesPath = "experiments/queries.jsonl",
  [string]$OutputPath = "experiments/benchmark.csv",
  [string]$GenerationModel = "gemma4:e2b",
  [switch]$NoLlm
)

$utf8 = [System.Text.UTF8Encoding]::new()
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
$env:PYTHONUTF8 = "1"

$args = @(
  "-m", "mededge_rag.cli", "eval",
  "--index", $IndexPath,
  "--queries", $QueriesPath,
  "--output", $OutputPath,
  "--generation-model", $GenerationModel
)

if ($NoLlm) {
  $args += "--no-llm"
}

python @args
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}
