$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop was not found. Install and start Docker Desktop first."
}
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Run scripts\setup_windows.ps1 first."
}
if (-not (Test-Path ".env")) {
    & .\.venv\Scripts\python.exe scripts\create_env.py --profile docker
}

$envText = Get-Content .env -Raw
if ($envText -notmatch "VECTOR_BACKEND=weaviate") {
    throw "The current .env is not the Docker profile. Back it up, then run create_env.py --profile docker --force."
}

docker compose up -d
Write-Host "Waiting for MySQL and Weaviate health checks..."
for ($i = 0; $i -lt 60; $i++) {
    $status = docker compose ps --format json | Out-String
    if ($status -match '"Health":"healthy"') {
        $healthyCount = ([regex]::Matches($status, '"Health":"healthy"')).Count
        if ($healthyCount -ge 2) { break }
    }
    Start-Sleep -Seconds 2
}

& .\.venv\Scripts\python.exe -m eci.cli init-db
& .\.venv\Scripts\python.exe scripts\apply_mysql_views.py
& .\.venv\Scripts\python.exe -m eci.cli ingest data\raw\complaints_raw.csv
& .\.venv\Scripts\python.exe -m eci.cli health

Write-Host "Enterprise local stack is ready."
Write-Host "Start the UI with scripts\run_demo.ps1"
