param(
    [string]$SiteKey = "",
    [string]$SecretKey = ""
)
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

Write-Warning 'Cloudflare Turnstile is no longer used by AVAN login.'
Write-Host 'AVAN now uses the self-hosted ALTCHA-compatible Anti-Bot container.' -ForegroundColor Cyan
Write-Host 'Run .\scripts\init-security.ps1 and rebuild the Docker stack; no external CAPTCHA keys are required.' -ForegroundColor Green

if ($SiteKey -or $SecretKey) {
    Write-Host 'The supplied Turnstile keys were ignored and were not written to .secrets.' -ForegroundColor Yellow
}
