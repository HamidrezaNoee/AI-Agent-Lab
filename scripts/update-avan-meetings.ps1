[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ProjectName,
    [Parameter(Mandatory=$true)][string[]]$ComposeFiles,
    [switch]$IncludeIdentity,
    [ValidateRange(60,1800)][int]$TimeoutSeconds = 600
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$composeArgs = @('compose','-p',$ProjectName)
foreach ($file in $ComposeFiles) {
    if (-not (Test-Path -LiteralPath $file)) { throw "Compose file missing: $file" }
    $composeArgs += @('-f',$file)
}
& docker @composeArgs config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose configuration is invalid.' }
$existing = & docker @composeArgs ps -a -q avan
if ($LASTEXITCODE -ne 0 -or -not $existing) {
    throw 'Existing AVAN container not found. Pass the exact project name and Compose files used by your installation; no new installation was created.'
}
$services = @('avan')
if ($IncludeIdentity) { $services = @('keycloak','avan') }
& docker @composeArgs up -d --no-deps --build --wait --wait-timeout $TimeoutSeconds @services
if ($LASTEXITCODE -ne 0) {
    & docker @composeArgs ps
    throw 'Update/readiness failed. Keep volumes and secrets; inspect service logs before retrying.'
}
& docker @composeArgs exec -T avan python -c "from commercial.secretary_catalog import _compile_pair; from commercial.secretary_ai_context import MAX_CONTEXT_CHARS; import json,pathlib; p=json.loads(pathlib.Path('/app/commercial/secretary_pack_reference.json').read_text()); assert len(_compile_pair(p['meeting'],p['action'])['stages'])==7; assert MAX_CONTEXT_CHARS==48000; print('Reviewed seven-stage pack is packaged. Live BPMS activation is still required.')"
if ($LASTEXITCODE -ne 0) { throw 'Packaged meeting components failed validation.' }
& docker @composeArgs ps
Write-Host 'Open AVAN > Management > BPMS connections > Process settings; activate the reviewed version-7 meeting/action pack.'
Write-Host 'Then verify user bindings and personal OAuth for secretary, chair and action owner. No users or live cases were modified by this script.'
