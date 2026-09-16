@echo off
setlocal
cd /d "%~dp0"
docker compose -f compose.preview.yml stop
echo Project data has not been deleted.
pause
