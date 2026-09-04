# ConcoursComposer 실행 - 서버를 띄우고 브라우저를 연다.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "먼저 .\install.ps1 을 실행하라." -ForegroundColor Red; exit 1
}
$port = if ($env:PORT) { $env:PORT } else { "8000" }
Write-Host "ConcoursComposer 를 http://localhost:$port 에서 연다. 끄려면 Ctrl+C." -ForegroundColor White
Start-Job { Start-Sleep 2; Start-Process "http://localhost:$using:port/" } | Out-Null
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir server --host 127.0.0.1 --port $port
