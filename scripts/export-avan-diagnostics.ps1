param(
  [string]$Repository = 'D:\A Project\17 meeting ai agent\Azure\AVAN-Git-Live-20260927',
  [string]$Project = 'avan-production',
  [switch]$Push
)
$ErrorActionPreference = 'Stop'
Push-Location $Repository
try {
  # Export the allowlisted diagnostic stream, never Docker logs or environment.
  $raw = & docker compose -p $Project -f compose.yaml -f compose.pm-local.yaml exec -T avan python -m commercial.diagnostics
  if ($LASTEXITCODE -ne 0) { throw 'Diagnostic export failed. The AVAN container must be running.' }
  $report = ($raw -join "`n") | ConvertFrom-Json
  if ($report.schema -ne 1 -or $report.includes_payloads -ne $false) { throw 'Unexpected diagnostic schema.' }
  $allowed = @('at','request_id','method','route','phase','error_type','outcome','status','upstream_status','duration_ms','bytes','count','stack')
  foreach ($row in $report.runtime) {
    foreach ($property in $row.PSObject.Properties.Name) {
      if ($property -notin $allowed) { throw "Unreviewed diagnostic property: $property" }
    }
  }
  if ($Push) {
    & git diff --cached --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Commit or unstage existing staged changes before using -Push.' }
    $branch = & git branch --show-current
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($branch)) { throw 'A named Git branch is required.' }
  }
  New-Item -ItemType Directory -Path 'temp-logs' -Force | Out-Null
  $stamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff')
  $relative = "temp-logs/avan-$stamp.json"
  $json = $report | ConvertTo-Json -Depth 12
  [IO.File]::WriteAllText((Join-Path (Get-Location) $relative), $json, [Text.UTF8Encoding]::new($false))
  Write-Host "Saved $relative"
  if ($Push) {
    & git add -- $relative
    if ($LASTEXITCODE -ne 0) { throw 'git add failed.' }
    & git commit -m "support: AVAN diagnostics $stamp" -- $relative
    if ($LASTEXITCODE -ne 0) { throw 'git commit failed.' }
    & git push origin $branch
    if ($LASTEXITCODE -ne 0) { throw 'git push failed; local diagnostic commit is preserved.' }
  }
} finally {
  Pop-Location
}
