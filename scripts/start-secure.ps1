param([switch]$Build = $true)
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

& (Join-Path $PSScriptRoot 'init-security.ps1')

if ($Build) { docker compose up -d --build } else { docker compose up -d }
if ($LASTEXITCODE -ne 0) { throw "docker compose failed: $LASTEXITCODE" }

function Test-Url([string]$Url) {
    try {
        $r = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 4
        return $r.StatusCode -eq 200
    } catch { return $false }
}

$kcReady=$false
for($i=0;$i -lt 60;$i++){
    if(Test-Url 'http://127.0.0.1:8181/realms/avan/.well-known/openid-configuration'){
        $kcReady=$true;break
    }
    Start-Sleep -Seconds 2
}
if(-not $kcReady){
    docker compose ps -a
    docker compose logs --tail=150 keycloak
    throw 'AVAN identity service did not become ready.'
}

$appReady=$false
for($i=0;$i -lt 40;$i++){
    if(Test-Url 'http://127.0.0.1:8188/health'){$appReady=$true;break}
    Start-Sleep -Seconds 2
}
if(-not $appReady){
    docker compose ps -a
    docker compose logs --tail=200 avan
    throw 'AVAN application did not become ready.'
}

Write-Host ''
Write-Host 'AVAN is running.' -ForegroundColor Green
Write-Host 'GodAdmin: http://127.0.0.1:8188/admin/'
Write-Host 'Workspace: http://127.0.0.1:8188/'
Write-Host ''
Write-Host 'GodAdmin bootstrap credential (shown once):' -ForegroundColor Yellow
docker compose exec -T avan python -m commercial.setup_console --take-bootstrap
