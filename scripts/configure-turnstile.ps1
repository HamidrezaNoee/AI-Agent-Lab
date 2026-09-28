param(
    [Parameter(Mandatory=$true)][string]$SiteKey,
    [Parameter(Mandatory=$true)][string]$SecretKey
)
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

if ([string]::IsNullOrWhiteSpace($SiteKey) -or [string]::IsNullOrWhiteSpace($SecretKey)) {
    throw 'Turnstile SiteKey and SecretKey are required.'
}
if ($SiteKey.Contains("`r") -or $SiteKey.Contains("`n") -or
    $SecretKey.Contains("`r") -or $SecretKey.Contains("`n")) {
    throw 'Turnstile credentials must be single-line values.'
}
$testSite = '1x00000000000000000000AA'
$testSecret = '1x0000000000000000000000000000000AA'
if ($SiteKey -eq $testSite -or $SecretKey -eq $testSecret) {
    throw 'Development Turnstile keys are not accepted by this production configuration command.'
}

$secretDir = Join-Path (Get-Location) '.secrets'
New-Item -ItemType Directory -Path $secretDir -Force | Out-Null
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText((Join-Path $secretDir 'avan-turnstile-site-key'), $SiteKey.Trim(), $utf8)
[System.IO.File]::WriteAllText((Join-Path $secretDir 'avan-turnstile-secret-key'), $SecretKey.Trim(), $utf8)

$currentIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
& icacls $secretDir /inheritance:r | Out-Null
& icacls $secretDir /grant:r "${currentIdentity}:(OI)(CI)F" "SYSTEM:(OI)(CI)F" | Out-Null
Get-ChildItem $secretDir -File | ForEach-Object {
    & icacls $_.FullName /inheritance:r | Out-Null
    & icacls $_.FullName /grant:r "${currentIdentity}:F" "SYSTEM:F" | Out-Null
}
Write-Host 'Cloudflare Turnstile production credentials stored as protected Docker secrets.' -ForegroundColor Green
Write-Host 'Rebuild the AVAN and Keycloak containers to activate them.' -ForegroundColor Cyan
