# Windows PowerShell 5.1+/PowerShell 7 Docker preview smoke test.
# Tests only the 127.0.0.1 fictional API. No SQL/Keycloak/ProcessMaker data.
$ErrorActionPreference = "Stop"
$base = "http://127.0.0.1:8090"

$health = Invoke-RestMethod -Uri "$base/health" -TimeoutSec 8
if ($health.status -ne "up" -or $health.production_data -ne $false -or
    $health.real_login -ne $false) {
    throw "Preview health check failed or points to an unexpected non-fictional app."
}
$dataset = Invoke-RestMethod -Uri "$base/demo-data" -TimeoutSec 8
if ($dataset.synthetic -ne $true -or $dataset.count -ne 100 -or
    @($dataset.scenarios).Count -ne 100) {
    throw "The app did not return the expected 100 synthetic meetings."
}
$actionCount = 0
foreach ($meeting in $dataset.scenarios) {
    $actionCount += @($meeting.actions).Count
}
if ($actionCount -ne 300) {
    throw "Expected 300 fictional actions but got $actionCount"
}

$catalog = Invoke-RestMethod -Uri "$base/demo-questions" -TimeoutSec 8
if (@($catalog.questions).Count -ne 8) {
    throw "The eight supported Persian management questions were not published."
}
foreach ($question in $catalog.questions) {
    $json = @{question=[string]$question} | ConvertTo-Json -Compress
    $response = Invoke-RestMethod -Uri "$base/demo-ask" -Method Post -Body ([System.Text.Encoding]::UTF8.GetBytes($json)) -ContentType "application/json; charset=utf-8" -TimeoutSec 12
    if ($response.synthetic -ne $true -or $response.model_used -ne $false -or
        $response.meetings_considered -ne 100 -or
        $response.actions_considered -ne 300 -or
        [string]::IsNullOrWhiteSpace([string]$response.answer)) {
        throw "Unusable or non-fictional answer for question: $question"
    }
    Write-Host "PASS: $question" -ForegroundColor Green
}
Write-Host "PASS: Docker preview health, 100 fictional meetings, 300 actions, eight Persian answers." -ForegroundColor Cyan
Write-Host "Browse: http://127.0.0.1:8090" -ForegroundColor Cyan
