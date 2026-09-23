[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$PublicKey,[string]$Repo=(Split-Path $PSScriptRoot -Parent))
$ErrorActionPreference='Stop'
$text=[IO.File]::ReadAllText((Resolve-Path $PublicKey)).Replace("`r`n","`n").Trim()
if (-not $text.StartsWith('-----BEGIN PUBLIC KEY-----') -or $text.Contains('PRIVATE KEY')) { throw 'Choose the issuer PUBLIC key only.' }
$sha=[Security.Cryptography.SHA256]::Create()
try { $hash=([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::ASCII.GetBytes($text)))).Replace('-','').ToLowerInvariant() }
finally { $sha.Dispose() }
$target=Join-Path $Repo 'commercial/licensing/publisher-key.sha256'
[IO.File]::WriteAllText($target,$hash+[Environment]::NewLine,[Text.Encoding]::ASCII)
Write-Host 'Public key fingerprint pinned in publisher source. Rebuild the customer image before activation.'
