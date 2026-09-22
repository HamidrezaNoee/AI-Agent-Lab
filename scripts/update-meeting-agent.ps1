[CmdletBinding()]
param(
    [string]$SourceRepo = (Split-Path $PSScriptRoot -Parent),
    [string]$Destination = '',
    [switch]$ProcessMakerLocalHttp
)
$ErrorActionPreference = 'Stop'
$branch = 'feature/pm-native-agent-store-20260922'
$SourceRepo = (Resolve-Path $SourceRepo).Path
if (-not $Destination) { $Destination = Join-Path (Split-Path $SourceRepo -Parent) 'AI-Agent-Lab-Agent' }
if (Test-Path $Destination) { throw "Destination already exists: $Destination. Choose a new -Destination; existing work will not be overwritten." }
$secretSource = Join-Path $SourceRepo '.secrets'
foreach ($name in @('keycloak-db-password','avan-bff-client-secret','avan-provisioner-client-secret')) {
    if (-not (Test-Path (Join-Path $secretSource $name))) { throw "Existing installation secret is missing: $name. Use the original configured checkout as -SourceRepo." }
}
& git -C $SourceRepo fetch origin $branch
if ($LASTEXITCODE -ne 0) { throw 'Git fetch failed.' }
& git -C $SourceRepo worktree add --detach $Destination "origin/$branch"
if ($LASTEXITCODE -ne 0) { throw 'Could not create an isolated worktree.' }
# Reuse installation identity; never regenerate secrets or remove volumes.
Copy-Item -LiteralPath $secretSource -Destination (Join-Path $Destination '.secrets') -Recurse
$composeArgs = @('compose','-p','avan-production','-f',(Join-Path $Destination 'compose.yaml'))
# Preserve the currently running laptop exception when present.
$running = & docker ps --filter 'label=com.docker.compose.project=avan-production' --filter 'label=com.docker.compose.service=avan' --format '{{.ID}}'
if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop is not available.' }
$localHttp = [bool]$ProcessMakerLocalHttp
if ($running) {
    $configuration = & docker inspect --format '{{json .Config.Env}}' ($running | Select-Object -First 1)
    if ($LASTEXITCODE -ne 0) { throw 'Could not inspect the running installation.' }
    $localHttp = $localHttp -or (($configuration | ConvertFrom-Json) -contains 'AVAN_PM_ALLOW_LOCAL_HTTP=1')
}
if ($localHttp) { $composeArgs += @('-f',(Join-Path $Destination 'compose.pm-local.yaml')) }
# --no-deps updates only AVAN; SQL, identity service, MTG and named volumes stay intact.
& docker @composeArgs up -d --build --no-deps --wait avan
if ($LASTEXITCODE -ne 0) { throw 'AVAN update failed. Review docker compose logs; do not remove volumes.' }
Write-Host "Updated source: $Destination"
Write-Host 'Open http://127.0.0.1:8188. Configure the dedicated Agent SQL database, ProcessMaker MySQL, then AI in GodAdmin.'
