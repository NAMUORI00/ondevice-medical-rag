param(
  [string]$IndexPath = "data/index/aihub_expert_sample_index.json",
  [string]$Question = "임신 중 복통이 있으면 어떻게 해야 하나요?",
  [string]$Model = "gemma3:4b"
)

if (-not $env:OLLAMA_API_KEY) {
  throw "Set OLLAMA_API_KEY before running this script."
}

$env:OLLAMA_HOST = "https://ollama.com"
$env:OLLAMA_MODEL = $Model
python -m mededge_rag.cli ask --index $IndexPath --question $Question --json
