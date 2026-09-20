[CmdletBinding()]
param(
    [switch]$RequireRomMUsers
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$composeFile = Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone11.yml"
$environmentFile = Join-Path $repositoryRoot ".env.milestone11"
if (-not (Test-Path -LiteralPath $environmentFile)) {
    throw "Run milestone11-start.ps1 first"
}

$settings = @{}
Get-Content -LiteralPath $environmentFile | ForEach-Object {
    if ($_ -match '^([^#=]+)=(.*)$') { $settings[$Matches[1]] = $Matches[2] }
}
$headers = @{ Authorization = "Bearer $($settings.M11_BOOTSTRAP_TOKEN)" }

$authBase = "http://auth.127.0.0.1.nip.io:9000"
$expectedIssuer = "$authBase/application/o/romm/"
$discovery = Invoke-RestMethod `
    -Uri "${expectedIssuer}.well-known/openid-configuration"
if ($discovery.issuer -ne $expectedIssuer) {
    throw "Unexpected OIDC issuer: $($discovery.issuer)"
}
if ($discovery.authorization_endpoint -notlike "*/application/o/authorize/") {
    throw "OIDC authorization endpoint is missing"
}

$provider = Invoke-RestMethod `
    -Uri "http://127.0.0.1:9000/api/v3/providers/oauth2/?name=Retro%20Arcade%20RomM%20OIDC" `
    -Headers $headers
$expectedCallback = "$($settings.M11_ROMM_URL)/api/oauth/openid"
if ($provider.pagination.count -ne 1 -or
    $provider.results[0].redirect_uris.Count -ne 1 -or
    $provider.results[0].redirect_uris[0].matching_mode -ne "strict" -or
    $provider.results[0].redirect_uris[0].url -ne $expectedCallback) {
    throw "authentik does not have the one exact RomM callback"
}

docker compose --env-file $environmentFile --file $composeFile exec -T romm `
    curl --fail --silent --show-error --max-time 10 `
    "http://auth.127.0.0.1.nip.io:9000/application/o/romm/.well-known/openid-configuration" `
    | Out-Null
if ($LASTEXITCODE -ne 0) { throw "RomM cannot reach the browser-visible OIDC issuer" }

$uids = @()
foreach ($username in @("player-one", "player-two")) {
    $result = Invoke-RestMethod `
        -Uri "http://127.0.0.1:9000/api/v3/core/users/?username=$username" `
        -Headers $headers
    if ($result.pagination.count -ne 1) { throw "Expected one authentik user named $username" }
    if (-not $result.results[0].attributes.email_verified) {
        throw "$username is not marked as email verified"
    }
    $uids += $result.results[0].uid
}
if ($uids[0] -eq $uids[1]) { throw "Test users do not have distinct stable authentik IDs" }

$redirectHandler = [Net.Http.HttpClientHandler]::new()
$redirectHandler.AllowAutoRedirect = $false
$redirectClient = [Net.Http.HttpClient]::new($redirectHandler)
try {
    $login = $redirectClient.GetAsync(
        "http://romm.127.0.0.1.nip.io:8095/api/login/openid"
    ).GetAwaiter().GetResult()
    if ([int]$login.StatusCode -notin @(302, 307)) {
        throw "RomM did not begin an OIDC redirect"
    }
    $location = $login.Headers.Location.AbsoluteUri
} finally {
    $redirectClient.Dispose()
    $redirectHandler.Dispose()
}
if ($location -notlike "http://auth.127.0.0.1.nip.io:9000/application/o/authorize/*") {
    throw "RomM redirected to an unexpected authorization endpoint"
}

$query = [Web.HttpUtility]::ParseQueryString(([Uri]$location).Query)
if ($query.Get("response_type") -ne "code" -or -not $query.Get("state") -or -not $query.Get("nonce")) {
    throw "RomM did not request a state- and nonce-bound authorization code"
}

if ($RequireRomMUsers) {
    $sql = "SELECT id, username, email FROM users WHERE email IN " +
        "('$($settings.M11_TEST_USER_A_EMAIL)','$($settings.M11_TEST_USER_B_EMAIL)') ORDER BY email;"
    $rows = docker compose --env-file $environmentFile --file $composeFile exec -T `
        romm-database mariadb --batch --skip-column-names -uromm `
        "-p$($settings.M11_ROMM_DB_PASSWORD)" romm -e $sql
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect RomM identity rows" }
    $records = @($rows | Where-Object { $_ -match '\S' })
    if ($records.Count -ne 2) {
        throw "Expected exactly two RomM OIDC users; complete both browser sign-ins first"
    }
    foreach ($record in $records) {
        $fields = $record -split "`t"
        if ($fields[1] -notmatch '^[0-9a-f]{64}$') {
            throw "RomM username is not authentik's hashed stable OIDC subject"
        }
    }
}

Write-Host "Milestone 11 automated identity checks passed."
if (-not $RequireRomMUsers) {
    Write-Host "After each test user signs in twice, rerun with -RequireRomMUsers."
}
