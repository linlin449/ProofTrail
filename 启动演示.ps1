$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONUTF8 = '1'
uv sync --locked --extra dev --group dev
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed' }
npm ci --ignore-scripts
if ($LASTEXITCODE -ne 0) { throw 'Compiler dependency installation failed' }
npm run compile
if ($LASTEXITCODE -ne 0) { throw 'Contract compilation failed' }
Write-Output 'ProofTrail: http://127.0.0.1:8765 (local EVM; not Monad deployment)'
uv run python -m prooftrail serve --host 127.0.0.1 --port 8765
