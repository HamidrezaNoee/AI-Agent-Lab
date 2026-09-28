$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

$secretDir = Join-Path (Get-Location) '.secrets'
New-Item -ItemType Directory -Path $secretDir -Force | Out-Null

function New-StrongSecret([int]$Bytes = 48) {
    $buffer = New-Object byte[] $Bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($buffer) } finally { $rng.Dispose() }
    return [Convert]::ToBase64String($buffer).TrimEnd('=').Replace('+','-').Replace('/','_')
}

function Write-SecretOnce([string]$Name, [string]$Value) {
    $path = Join-Path $secretDir $Name
    if (-not (Test-Path $path)) {
        [System.IO.File]::WriteAllText($path, $Value, (New-Object System.Text.UTF8Encoding($false)))
    }
}

Write-SecretOnce 'keycloak-db-password' (New-StrongSecret 48)
Write-SecretOnce 'avan-bff-client-secret' (New-StrongSecret 64)
Write-SecretOnce 'avan-provisioner-client-secret' (New-StrongSecret 64)
Write-SecretOnce 'avan-sql-sa-password' ('Avan1!' + (New-StrongSecret 48))
# Official Cloudflare Turnstile development keys. Production HTTPS refuses them.
Write-SecretOnce 'avan-turnstile-site-key' '1x00000000000000000000AA'
Write-SecretOnce 'avan-turnstile-secret-key' '1x0000000000000000000000000000000AA'

$currentIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
& icacls $secretDir /inheritance:r | Out-Null
& icacls $secretDir /grant:r "${currentIdentity}:(OI)(CI)F" "SYSTEM:(OI)(CI)F" | Out-Null
Get-ChildItem $secretDir -File | ForEach-Object {
    & icacls $_.FullName /inheritance:r | Out-Null
    & icacls $_.FullName /grant:r "${currentIdentity}:F" "SYSTEM:F" | Out-Null
}
Write-Host 'AVAN internal identity and database secrets initialized.' -ForegroundColor Green
Write-Host 'No SQL Server, ProcessMaker or customer password is stored in .env.' -ForegroundColor Green
Write-Host 'Turnstile development keys are installed for localhost only. Replace them before HTTPS production deployment.' -ForegroundColor Yellow
