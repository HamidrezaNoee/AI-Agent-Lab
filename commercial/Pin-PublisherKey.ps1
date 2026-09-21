# Publisher-only release preparation: pin the trusted public verification key.
# Do not copy the private issuer key into this repository or the Docker image.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$PublicKeyPath)
$ErrorActionPreference='Stop'
$key=(Resolve-Path $PublicKeyPath).Path
$raw=[IO.File]::ReadAllText($key)
if ($raw -notmatch '-----BEGIN PUBLIC KEY-----' -or
    $raw -match 'PRIVATE KEY' -or $raw.Length -gt 10000) {
    throw 'Only a publisher PUBLIC PEM file may be pinned.'
}
$pin=(Get-FileHash -LiteralPath $key -Algorithm SHA256).Hash.ToLowerInvariant()
$target=Join-Path $PSScriptRoot 'licensing\publisher-key.sha256'
[IO.File]::WriteAllText($target,$pin+[char]10,(New-Object Text.UTF8Encoding $false))
Write-Host 'Publisher public-key fingerprint pinned for this software build.' -ForegroundColor Green
Write-Host 'No private signing key was read, copied, or included.' -ForegroundColor Green
Write-Host 'Rebuild the verified AVAN image; unpinned releases must refuse license activation.' -ForegroundColor Yellow
