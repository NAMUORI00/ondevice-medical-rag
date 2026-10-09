param(
  [string]$IndexPath = "data/index/mededge_index.json",
  [string]$Question = ""
)

$utf8 = [System.Text.UTF8Encoding]::new()
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
$env:PYTHONUTF8 = "1"

if (-not $Question) {
  $Question = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("7JWE7J206rCAIOqzoOyXtOydvCDrlYwg7Ja47KCcIOydkeq4ieyLpOyXkCDqsIDslbwg7ZWY64KY7JqUPw=="))
}

python -m mededge_rag.cli ask --index $IndexPath --question $Question
