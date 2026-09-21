# AVAN local ProcessMaker 3 OAuth helper. Do not save or print secrets.
# Intended only for localhost:84; this does NOT bypass AVAN's HTTPS requirement.
[CmdletBinding()]
param(
    [string]$BaseUrl = "http://localhost:84",
    [string]$Workspace = "workflow"
)
$ErrorActionPreference = "Stop"
$client = $null
$clientSecretPlain = $null
$passwordPlain = $null
$token = $null
try {
    $uri = [Uri]$BaseUrl
    if ($uri.Scheme -notin @("http","https") -or
        $uri.Host -notin @("localhost","127.0.0.1","::1") -or
        $uri.UserInfo -or $uri.Query -or $uri.Fragment -or
        $uri.AbsolutePath -ne "/") {
        throw "Only a local ProcessMaker root URL (for example http://localhost:84) is allowed."
    }
    if ($Workspace -notmatch '^[a-zA-Z0-9_-]{1,48}$') {
        throw "Invalid workspace."
    }
    $clientId = Read-Host "ProcessMaker OAuth Client ID"
    $clientSecret = Read-Host "ProcessMaker OAuth Client Secret" -AsSecureString
    $username = Read-Host "ProcessMaker API Username (e.g. administrator)"
    $password = Read-Host "ProcessMaker API Password" -AsSecureString

    function To-Plain([SecureString]$SecureValue) {
        $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
        try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
        finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
    }
    $clientSecretPlain = To-Plain $clientSecret
    $passwordPlain = To-Plain $password
    $clientId = $clientId.Trim()
    $username = $username.Trim()
    if (-not $clientId -or -not $clientSecretPlain -or -not $username -or -not $passwordPlain) {
        throw "All OAuth and user fields are required."
    }

    $handler = [System.Net.Http.HttpClientHandler]::new()
    $handler.AllowAutoRedirect = $false
    $handler.UseProxy = $false
    $client = [System.Net.Http.HttpClient]::new($handler)
    $client.Timeout = [TimeSpan]::FromSeconds(15)
    $base = $BaseUrl.TrimEnd('/')
    $form = [System.Collections.Generic.Dictionary[string,string]]::new()
    $form.Add("grant_type","password")
    $form.Add("scope","*")
    $form.Add("client_id",$clientId)
    $form.Add("client_secret",$clientSecretPlain)
    $form.Add("username",$username)
    $form.Add("password",$passwordPlain)
    $body = [System.Net.Http.FormUrlEncodedContent]::new($form)
    Write-Host "Step 1: requesting OAuth token..."
    $response = $client.PostAsync("$base/$Workspace/oauth2/token",$body).GetAwaiter().GetResult()
    $status = [int]$response.StatusCode
    if ($status -ne 200) { throw "OAuth token endpoint returned HTTP $status. Check OAuth app, grant and login credentials." }
    $json = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
    if ($json.Length -gt 20000) { throw "Unexpected large token response." }
    $issued = $json | ConvertFrom-Json
    $token = [string]$issued.access_token
    if ($token.Length -lt 8 -or $token -match '[\r\n]') { throw "No valid access_token in OAuth response." }
    Write-Host "OAuth token received; it will not be printed."

    Write-Host "Step 2: checking GET /api/1.0/$Workspace/users ..."
    $usersUrl = "$base/api/1.0/$Workspace/users?status=all&start=0&limit=1"
    $request = [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::Get, $usersUrl)
    $request.Headers.Authorization = [System.Net.Http.Headers.AuthenticationHeaderValue]::new("Bearer",$token)
    $request.Headers.Accept.ParseAdd("application/json")
    $usersResponse = $client.SendAsync($request).GetAwaiter().GetResult()
    $usersStatus = [int]$usersResponse.StatusCode
    if ($usersStatus -ne 200) {
        throw "ProcessMaker users API returned HTTP $usersStatus. Check user-list permission and token."
    }
    $usersJson = $usersResponse.Content.ReadAsStringAsync().GetAwaiter().GetResult()
    if ($usersJson.Length -gt 20000 -or -not ($usersJson.TrimStart().StartsWith('[') -or $usersJson.TrimStart().StartsWith('{'))) {
        throw "Unexpected ProcessMaker users response."
    }
    $null = $usersJson | ConvertFrom-Json
    Set-Clipboard -Value $token
    Write-Host "SUCCESS: token was copied to Clipboard; not saved to disk." -ForegroundColor Green
    Write-Host "Remember: AVAN's current ProcessMaker form requires a trusted HTTPS URL."
    Write-Host "Clear clipboard when finished: Set-Clipboard -Value ''"
}
catch {
    Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Do not share passwords, Client Secret, access_token or QR/OTP codes."
}
finally {
    if ($client) { $client.Dispose() }
    $clientSecretPlain = $null; $passwordPlain = $null; $token = $null
}
