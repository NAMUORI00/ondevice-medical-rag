param(
  [string]$InputPath = "data/sample/medical_qa_sample.jsonl",
  [string]$IndexPath = "data/index/mededge_index.json"
)

python -m mededge_rag.cli ingest --input $InputPath --index $IndexPath
