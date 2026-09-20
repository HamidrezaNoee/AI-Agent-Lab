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
$parentVenvPython = Join-Path (Split-Path $repo -Parent) '.venv\Scripts\python.exe'
if (Test-Path $venvPython) {
    $python = $venvPython
} elseif (Test-Path $parentVenvPython) {
    $python = $parentVenvPython
} else {
    throw "Python venv not found. Expected in repo\.venv or next to the repo."
}
& $python -c 'import fastapi,uvicorn,cryptography,jwt,httpx'
if ($LASTEXITCODE -ne 0) {
    throw "Missing Python requirements. Install inside the venv with: & `"$python`" -m pip install -r commercial/requirements.txt"
}
if (-not $SkipTests) {
    & $python -m unittest discover -s commercial/tests -v
    if ($LASTEXITCODE -ne 0) {
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
