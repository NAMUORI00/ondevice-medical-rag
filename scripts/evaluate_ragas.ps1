param(
  [string]$BenchmarkPath = "experiments/benchmark.csv",
  [string]$OutputPath = "experiments/ragas_results.csv",
  [string]$JudgeModel = "gemini-3-flash-preview:cloud",
  [string]$JudgeHost = "https://ollama.com/v1",
  [string]$EmbeddingModel = "",
  [string]$EmbeddingHost = "https://ollama.com/v1",
  [string]$Metrics = "answer_relevancy,faithfulness,context_precision,context_recall"
)

$utf8 = [System.Text.UTF8Encoding]::new()
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
$env:PYTHONUTF8 = "1"

$args = @(
  "-m", "mededge_rag.cli", "ragas",
  "--input", $BenchmarkPath,
  "--output", $OutputPath,
  "--judge-model", $JudgeModel,
  "--judge-host", $JudgeHost,
  "--embedding-host", $EmbeddingHost,
  "--metrics", $Metrics
)

if (-not [string]::IsNullOrWhiteSpace($EmbeddingModel)) {
  $args += @("--embedding-model", $EmbeddingModel)
}

python @args
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}
