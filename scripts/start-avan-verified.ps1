[CmdletBinding()]
param(
    [string[]]$ComposeFiles = @('compose.yaml', 'compose.pm-local.yaml'),
    [ValidateRange(60,1800)][int]$TimeoutSeconds = 600,
    [switch]$SkipBuild
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$composeArgs = @('compose', '-p', 'avan-production')
foreach ($file in $ComposeFiles) {
    if (-not (Test-Path -LiteralPath $file)) { throw "Compose file missing: $file" }
    $composeArgs += @('-f', $file)
}
function Invoke-DockerChecked {
    param([string[]]$DockerArgs)
    & docker @DockerArgs
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed (exit $LASTEXITCODE). Existing volumes and secrets were retained." }
}
Invoke-DockerChecked -DockerArgs @('info', '--format', '{{.ServerVersion}}')
Invoke-DockerChecked -DockerArgs ($composeArgs + @('config', '--quiet'))
if (-not $SkipBuild) {
    Invoke-DockerChecked -DockerArgs ($composeArgs + @('build', 'antibot', 'keycloak', 'avan'))
}
try {
    Invoke-DockerChecked -DockerArgs ($composeArgs + @('up', '-d', '--wait', '--wait-timeout', "$TimeoutSeconds", 'avan'))
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $ready = $false
    do {
        try {
            $oidc = Invoke-RestMethod -Uri 'http://127.0.0.1:8181/realms/avan/.well-known/openid-configuration' -TimeoutSec 10
            if ($oidc.issuer -ne 'http://auth.localhost:8181/realms/avan' -or -not $oidc.authorization_endpoint) {
                throw 'The expected AVAN realm discovery document was not returned.'
            }
            $health = Invoke-WebRequest -Uri 'http://127.0.0.1:8188/health' -UseBasicParsing -TimeoutSec 10
            $ready = ($health.StatusCode -eq 200)
        } catch {
            Write-Host 'Waiting for AVAN realm initialization...'
        }
        if (-not $ready) { Start-Sleep -Seconds 5 }
    } while (-not $ready -and (Get-Date) -lt $deadline)
    if (-not $ready) { throw 'AVAN readiness timed out. Inspect logs below; do not reset volumes.' }
    Invoke-DockerChecked -DockerArgs ($composeArgs + @('ps'))
    Write-Host 'AVAN realm and app are ready: http://127.0.0.1:8188/auth/login'
    Write-Host 'Readiness does not verify user credentials, BPMS bindings or a complete meeting workflow.'
} catch {
    & docker @composeArgs logs --tail 100 keycloak keycloak-realm-theme-init avan
    throw
}
