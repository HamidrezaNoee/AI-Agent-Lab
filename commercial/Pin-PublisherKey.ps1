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
# Canonicalize CRLF and trailing newlines; the admin textarea supplies the
# same canonical PEM, so browser line endings cannot cause false mismatch.
$normalized=$raw.Replace(([string][char]13+[char]10),[string][char]10).Trim()
$hash=[System.Security.Cryptography.SHA256]::Create()
try {
    $bytes=[System.Text.Encoding]::UTF8.GetBytes($normalized)
    $pin=([BitConverter]::ToString($hash.ComputeHash($bytes))).Replace("-","").ToLowerInvariant()
} finally { $hash.Dispose() }
$target=Join-Path $PSScriptRoot 'licensing\publisher-key.sha256'
[IO.File]::WriteAllText($target,$pin+[char]10,([System.Text.UTF8Encoding]::new($false)))
Write-Host 'Publisher public-key fingerprint pinned for this software build.' -ForegroundColor Green
Write-Host 'No private signing key was read, copied, or included.' -ForegroundColor Green
Write-Host 'Rebuild the verified AVAN image; unpinned releases must refuse license activation.' -ForegroundColor Yellow
