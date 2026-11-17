# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8516,
    [switch]$VerifyWebIQ
)

$ErrorActionPreference = 'Stop'
$sample = Join-Path $PSScriptRoot 'samples\python\market-briefing'
$python = Join-Path $sample '.venv\Scripts\python.exe'
$configPath = Join-Path $sample 'config.local.json'
if (-not (Test-Path -LiteralPath $configPath)) {
    throw 'Create config.local.json with your model settings first. See DEMO.md.'
}
$config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json
if ($config.azure_openai.auth_mode -ne 'azure-cli') {
    throw 'This local launcher expects azure_openai.auth_mode to be azure-cli.'
}
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    throw "Port $Port is already in use. Choose another port with -Port."
}
& (Join-Path $PSScriptRoot 'Start-Demo.ps1') -SetupOnly
if ($LASTEXITCODE -ne 0) {
    throw 'Demo environment setup failed.'
}

Write-Host 'Web IQ live setup - keys are never saved to a file.'
Write-Host 'First connect your Web IQ resource in https://webiq.microsoft.ai/profiles'
Write-Host 'Then create or copy its API key with both Web and News access.'
Write-Host "Model deployment: $($config.azure_openai.deployment) (Azure CLI sign-in)"
Write-Host 'Your existing Azure sign-in must have inference access to the model.'

$previousWebKey = $env:WEBIQ_API_KEY
$secureKey = $null
try {
    if ([string]::IsNullOrWhiteSpace($env:WEBIQ_API_KEY)) {
        $secureKey = Read-Host 'Paste Web IQ API key here (hidden), then press Enter' -AsSecureString
        $env:WEBIQ_API_KEY = [System.Net.NetworkCredential]::new('', $secureKey).Password.Trim()
        if ([string]::IsNullOrWhiteSpace($env:WEBIQ_API_KEY)) {
            throw 'No Web IQ key was entered. Nothing was saved or started.'
        }
    }

    if ($VerifyWebIQ) {
        Write-Host 'Checking one Web and one News request (billable; no retries)...'
        @'
import os
from webiq import RetryPolicy, WebIQClient
from webiq.errors import WebIQError
from webiq.types import ContentFormat

try:
    with WebIQClient(
        api_key=os.environ["WEBIQ_API_KEY"], timeout=20.0,
        retry=RetryPolicy(max_retries=0),
    ) as client:
        for label, search in (("Web", client.web.search), ("News", client.news.search)):
            search(
                "North American energy market latest developments", max_results=1,
                language="en", region="US", content_format=ContentFormat.passage,
                max_length=500,
            )
            print(f"{label} access verified.")
except WebIQError as error:
    status = getattr(error, "status_code", None)
    print(f"Web IQ validation failed: {type(error).__name__}; HTTP status: {status}.")
    print("Check the portal connection and both entitlements. No demo server was started.")
    raise SystemExit(1)
'@ | & $python -
        if ($LASTEXITCODE -ne 0) {
            throw 'Web IQ validation failed. Review the status above; the key was not saved.'
        }
    }

    Write-Host "Starting Web IQ Insight Studio at http://127.0.0.1:$Port"
    Write-Host 'Close this window or press Ctrl+C to stop the server and discard its key.'
    & (Join-Path $PSScriptRoot 'Start-Demo.ps1') -Port $Port
}
finally {
    $env:WEBIQ_API_KEY = $previousWebKey
    if ($null -ne $secureKey) {
        $secureKey.Dispose()
    }
}
