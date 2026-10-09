param(
  [string]$RagasPath = "experiments/ragas_results.csv",
  [string]$DeltaPath = "experiments/answer_relevancy_delta.csv",
  [string]$SummaryPath = "experiments/answer_relevancy_summary.csv",
  [string]$BaselineCondition = "llm_only",
  [string]$RagCondition = "rag_top3",
  [double]$Confidence = 0.95,
  [int]$BootstrapSamples = 10000,
  [int]$Seed = 13
)

$utf8 = [System.Text.UTF8Encoding]::new()
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
$env:PYTHONUTF8 = "1"

$args = @(
  "-m", "mededge_rag.cli", "relevancy-delta",
  "--input", $RagasPath,
  "--delta-output", $DeltaPath,
  "--summary-output", $SummaryPath,
  "--baseline-condition", $BaselineCondition,
  "--rag-condition", $RagCondition,
  "--confidence", $Confidence,
  "--bootstrap-samples", $BootstrapSamples,
  "--seed", $Seed
)

python @args
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}
