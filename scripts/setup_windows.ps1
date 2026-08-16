$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' was not found. Install Python 3.11 first."
}

if (-not (Test-Path ".venv")) {
    py -3.11 -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
& .\.venv\Scripts\python.exe -m pip install -e . --no-deps --no-build-isolation

if (-not (Test-Path ".env")) {
    & .\.venv\Scripts\python.exe scripts\create_env.py --profile portable
}

& .\.venv\Scripts\python.exe -m pytest
& .\.venv\Scripts\python.exe scripts\bootstrap_demo.py --reset

Write-Host ""
Write-Host "Setup complete. Start the application with:"
Write-Host ".\.venv\Scripts\python.exe -m streamlit run app.py"
