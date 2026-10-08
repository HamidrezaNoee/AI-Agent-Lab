# Run a locally compiled EXE when available, otherwise use the PowerShell helper.
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$exe = Join-Path $root "Avan-ProcessMaker-Token-Tool.exe"
$source = Join-Path $root "source"
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    if (Get-Command go -ErrorAction SilentlyContinue) {
        Write-Host "Building Windows executable locally from GitHub source..." -ForegroundColor Cyan
        Push-Location $source
        try {
            & go build -trimpath -ldflags="-s -w" -o $exe .
            if ($LASTEXITCODE -ne 0) { throw "Go compilation failed." }
        } finally {
            Pop-Location
        }
    } else {
        Write-Host "Go is not installed. Running the equivalent PowerShell token tool." -ForegroundColor Yellow
        & (Join-Path $root "Get-AvanPmToken.ps1")
        return
    }
}
Write-Host "Starting AVAN ProcessMaker Token Tool..." -ForegroundColor Cyan
& $exe
if ($LASTEXITCODE -ne 0) { throw "Token helper exited with error code $LASTEXITCODE" }
