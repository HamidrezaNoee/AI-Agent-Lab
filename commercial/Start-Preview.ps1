# Local fictional product preview only. NEVER bind public NIC or production data.
# Usage: powershell -ExecutionPolicy Bypass -File .\commercial\Start-Preview.ps1
[CmdletBinding()]
param(
    [switch]$SkipTests,
    [ValidateRange(1024,65535)][int]$Port = 8090
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $repo
$venvPython = Join-Path $repo '.venv\Scripts\python.exe'
$siblingVenvPython = Join-Path (Split-Path $repo -Parent) 'AI-Agent-Lab\.venv\Scripts\python.exe'
if (Test-Path $venvPython) {
    $python = $venvPython
} elseif (Test-Path $siblingVenvPython) {
    $python = $siblingVenvPython
} else {
    throw "Python venv not found. Expected in repo\.venv or sibling AI-Agent-Lab\.venv."
}
& $python -c 'import fastapi,uvicorn,cryptography,jwt,httpx'
if ($LASTEXITCODE -ne 0) {
    throw "Missing Python requirements. Install inside the venv with: & `"$python`" -m pip install -r commercial/requirements.txt"
}
if (-not $SkipTests) {
    # Legacy /v1 unit tests require their historical grant-only contract.
    # Test the /v2 closure separately, but do not inherit a live server flag
    # from the operator's PowerShell session into the whole test process.
    $previousV2 = $env:COMMERCIAL_V2_ONLY
    $previousChat = $env:COMMERCIAL_CHAT_ENABLED
    try {
        $env:COMMERCIAL_V2_ONLY = '0'
        $env:COMMERCIAL_CHAT_ENABLED = '0'
        & $python -m unittest discover -s commercial/tests -v
        $testExit = $LASTEXITCODE
    } finally {
        $env:COMMERCIAL_V2_ONLY = $previousV2
        $env:COMMERCIAL_CHAT_ENABLED = $previousChat
    }
    if ($testExit -ne 0) {
        throw 'Offline commercial tests FAILED; preview was not started.'
    }
}
$fontFolder = Join-Path $repo 'commercial\web\fonts'
if (-not ((Test-Path (Join-Path $fontFolder 'byekanplus-regular.ttf')) -and
          (Test-Path (Join-Path $fontFolder 'byekanplus-bold.ttf')))) {
    Write-Warning 'Optional BYekanPlus files missing: copy your own licensed fonts into commercial\web\fonts. Tahoma fallback is available; no font URLs will be requested.'
}
Write-Host ('Open http://127.0.0.1:' + $Port + ' and press Ctrl+C to stop.') -ForegroundColor Green
& $python -m uvicorn commercial.demo_preview:app --host 127.0.0.1 --port $Port
exit $LASTEXITCODE
