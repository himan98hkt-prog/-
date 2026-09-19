$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
Set-Location -LiteralPath $PSScriptRoot
$logPath = Join-Path $PSScriptRoot "studio-startup.log"

function Write-Step([string]$Message) {
    Write-Host "`n[Shorts Studio] $Message" -ForegroundColor Cyan
}

function Run-Docker([string[]]$Arguments) {
    & docker @Arguments 2>&1 | Tee-Object -FilePath $logPath -Append
    if ($LASTEXITCODE -ne 0) {
        throw "docker $($Arguments -join ' ') failed (exit $LASTEXITCODE)"
    }
}

try {
    "Shorts Studio startup - $(Get-Date -Format o)" | Set-Content -LiteralPath $logPath -Encoding UTF8
    Write-Step "Checking Docker Desktop"
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $docker) {
        throw "Docker command was not found. Install Docker Desktop, restart Windows, and run this file again."
    }
    & docker compose version 2>&1 | Tee-Object -FilePath $logPath -Append
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose is not available. Update Docker Desktop."
    }

    & docker info *> $null
    if ($LASTEXITCODE -ne 0) {
        $desktop = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
        if (Test-Path -LiteralPath $desktop) {
            Write-Step "Starting Docker Desktop. This can take several minutes."
            Start-Process -FilePath $desktop
        } else {
            throw "Docker Desktop is installed incorrectly or cannot be found."
        }
        $dockerReady = $false
        for ($attempt = 1; $attempt -le 90; $attempt++) {
            Start-Sleep -Seconds 2
            & docker info *> $null
            if ($LASTEXITCODE -eq 0) { $dockerReady = $true; break }
            if ($attempt % 10 -eq 0) { Write-Host "Waiting for Docker Desktop... $($attempt * 2) seconds" }
        }
        if (-not $dockerReady) {
            throw "Docker Desktop did not become ready. Open Docker Desktop and resolve the message shown there."
        }
    }

    Write-Step "Building and starting the application. The first run can take 5-15 minutes."
    Run-Docker @("compose", "-f", "compose.preview.yml", "up", "--build", "-d")

    Write-Step "Waiting for the application"
    $appReady = $false
    for ($attempt = 1; $attempt -le 90; $attempt++) {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:8765/health" -TimeoutSec 3
            if ($health.status -eq "ok" -and $health.database) { $appReady = $true; break }
        } catch {}
        Start-Sleep -Seconds 2
    }
    if (-not $appReady) {
        Write-Step "The application did not become ready. Saving container status and logs."
        & docker compose -f compose.preview.yml ps 2>&1 | Tee-Object -FilePath $logPath -Append
        & docker compose -f compose.preview.yml logs --tail 150 2>&1 | Tee-Object -FilePath $logPath -Append
        throw "Application health check failed."
    }

    Write-Step "Ready. Opening http://localhost:8765"
    Start-Process "http://localhost:8765"
    Write-Host "Keep Docker Desktop running while a video is being processed." -ForegroundColor Green
    Write-Host "If the browser does not open, enter http://localhost:8765 yourself."
    exit 0
} catch {
    $message = $_.Exception.Message
    "ERROR: $message" | Tee-Object -FilePath $logPath -Append
    Write-Host "`nCould not start Shorts Studio:" -ForegroundColor Red
    Write-Host $message -ForegroundColor Yellow
    Write-Host "`nDiagnostic log: $logPath"
    exit 1
}
