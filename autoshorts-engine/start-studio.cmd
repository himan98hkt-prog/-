@echo off
setlocal
cd /d "%~dp0"
docker info >nul 2>&1
if errorlevel 1 (
  echo Please install and start Docker Desktop, then run this file again.
  pause
  exit /b 1
)
docker compose -f compose.preview.yml up --build -d
if errorlevel 1 (
  echo Startup failed. Please copy the error shown above.
  pause
  exit /b 1
)
powershell -NoProfile -Command "$ready=$false; for($i=0;$i -lt 60;$i++){try{$r=Invoke-RestMethod http://localhost:8765/health -TimeoutSec 2; if($r.database){$ready=$true; break}}catch{}; Start-Sleep -Seconds 2}; if(-not $ready){exit 1}"
if errorlevel 1 (
  echo The API is not ready. Check: docker compose -f compose.preview.yml logs --tail 100 api
  pause
  exit /b 1
)
start "" "http://localhost:8765"
echo Shorts Studio is running. Keep Docker Desktop open while processing videos.
pause
