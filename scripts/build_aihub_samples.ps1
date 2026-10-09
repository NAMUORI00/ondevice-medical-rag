param(
  [string]$RequiredZip = "$HOME\Downloads\Sample.zip",
  [string]$ExpertZip = "$HOME\Downloads\Sample (1).zip"
)

python -m mededge_rag.cli ingest --input $RequiredZip --index data/index/aihub_required_sample_index.json --normalized-output data/index/aihub_required_sample.jsonl
python -m mededge_rag.cli ingest --input $ExpertZip --index data/index/aihub_expert_sample_index.json --normalized-output data/index/aihub_expert_sample.jsonl
