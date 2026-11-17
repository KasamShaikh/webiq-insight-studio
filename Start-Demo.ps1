# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8515,
    [switch]$SetupOnly
)

$ErrorActionPreference = 'Stop'
$sample = Join-Path $PSScriptRoot 'samples\python\market-briefing'
$environment = Join-Path $sample '.venv'
$python = Join-Path $environment 'Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python)) {
    py -3 -m venv $environment
    if ($LASTEXITCODE -ne 0) {
        throw 'Virtual environment creation failed. Install Python 3.11 or later.'
    }
}

& $python -c 'import streamlit, webiq_market_briefing' 2>$null
if ($LASTEXITCODE -ne 0) {
    & $python -m pip install -e "$sample[demo]"
    if ($LASTEXITCODE -ne 0) {
        throw 'Dependency installation failed. Review the pip output above.'
    }
}

if ($SetupOnly) {
    Write-Host 'Demo environment is ready. Run .\Start-Demo.ps1 to launch.'
    return
}

if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    throw "Port $Port is already in use. Choose another port with -Port."
}

Write-Host "Opening the local demo at http://127.0.0.1:$Port"
Push-Location -LiteralPath $sample
try {
    & $python -m streamlit run app.py --server.port $Port
    if ($LASTEXITCODE -ne 0) {
        throw 'The demo server stopped with an error.'
    }
}
finally {
    Pop-Location
}
