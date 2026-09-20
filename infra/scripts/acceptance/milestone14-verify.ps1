[CmdletBinding()]
param(
    [switch]$RequireRomMUsers,
    [switch]$RequireClean
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$environmentFile = Join-Path $repositoryRoot ".env.milestone14"
$composeFiles = @(
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone10.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone11.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone12.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone14.yml")
)
if (-not (Test-Path -LiteralPath $environmentFile)) { throw "Run milestone14-start.ps1 first" }
$settings = @{}
Get-Content -LiteralPath $environmentFile | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)=(.*)$') {
        $value = $Matches[2].Trim()
        if ($value.Length -ge 2 -and
            (($value.StartsWith("'") -and $value.EndsWith("'")) -or
            ($value.StartsWith('"') -and $value.EndsWith('"')))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $settings[$Matches[1].Trim()] = $value
    }
}
$arguments = @("compose", "--env-file", $environmentFile)
foreach ($file in $composeFiles) { $arguments += @("--file", $file) }
$publicBase = "https://$($settings.M14_PUBLIC_HOSTNAME)"
$authBase = "https://$($settings.M14_AUTH_HOSTNAME)"
$headers = @{ Authorization = "Bearer $($settings.M11_BOOTSTRAP_TOKEN)" }

$heartbeat = Invoke-WebRequest -Uri "$publicBase/api/heartbeat" -TimeoutSec 15
if ($heartbeat.StatusCode -ne 200) { throw "Public RomM heartbeat failed" }
$discovery = Invoke-RestMethod `
    -Uri "$authBase/application/o/romm/.well-known/openid-configuration" -TimeoutSec 15
$expectedIssuer = "$authBase/application/o/romm/"
if ($discovery.issuer -ne $expectedIssuer) { throw "Unexpected OIDC issuer: $($discovery.issuer)" }

$provider = Invoke-RestMethod `
    -Uri "$authBase/api/v3/providers/oauth2/?name=Retro%20Arcade%20RomM%20OIDC" `
    -Headers $headers -TimeoutSec 15
$expectedCallback = "$publicBase/api/oauth/openid"
if ($provider.pagination.count -ne 1 -or
    $provider.results[0].redirect_uris.Count -ne 1 -or
    $provider.results[0].redirect_uris[0].matching_mode -ne "strict" -or
    $provider.results[0].redirect_uris[0].url -ne $expectedCallback) {
    throw "authentik does not have the one exact public RomM callback"
}

& docker @($arguments + @("exec", "-T", "romm", "curl", "--fail", "--silent", "--show-error", "--max-time", "10", "$authBase/application/o/romm/.well-known/openid-configuration")) | Out-Null
if ($LASTEXITCODE -ne 0) { throw "RomM cannot reach the browser-visible OIDC issuer" }
& docker @($arguments + @("exec", "-T", "session-manager", "python", "-c", "import os,urllib.request; r=urllib.request.Request('http://romm:8080/api/multiplayer/health', headers={'X-External-Multiplayer-Token':os.environ['SESSION_MANAGER_ROMM_SERVICE_TOKEN']}); assert urllib.request.urlopen(r, timeout=5).status == 200"))
if ($LASTEXITCODE -ne 0) { throw "The private RomM resolver is unavailable" }
& docker @($arguments + @("exec", "-T", "turn-rest", "python", "-c", "import json,urllib.request; d=json.load(urllib.request.urlopen('http://127.0.0.1:8008/?service=turn&username=m14-verify&key=$($settings.M14_TURN_REST_API_KEY)',timeout=5)); assert d.get('username') and d.get('password') and d.get('uris') and d.get('ttl') == 3600"))
if ($LASTEXITCODE -ne 0) { throw "Private TURN credential minting failed" }

$managerId = & docker @($arguments + @("ps", "-q", "session-manager"))
$managerMounts = docker inspect $managerId --format "{{range .Mounts}}{{println .Source}}{{end}}"
if ($managerMounts -match "docker.sock") { throw "Session Manager has Docker socket access" }

if ($RequireRomMUsers) {
    $sql = "SELECT id, username, email FROM users WHERE email IN " +
        "('$($settings.M11_TEST_USER_A_EMAIL)','$($settings.M11_TEST_USER_B_EMAIL)') ORDER BY email;"
    $rows = & docker @($arguments + @("exec", "-T", "romm-database", "mariadb", "--batch", "--skip-column-names", "-uromm", "-p$($settings.M11_ROMM_DB_PASSWORD)", "romm", "-e", $sql))
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect RomM identity rows" }
    $records = @($rows | Where-Object { $_ -match '\S' })
    if ($records.Count -ne 2) { throw "Expected exactly two RomM OIDC users" }
}

if ($RequireClean) {
    $listed = & docker @($arguments + @("exec", "-T", "runtime-agent", "python", "-m", "retro_runtime.client", "list"))
    if ($LASTEXITCODE -ne 0 -or (($listed | ConvertFrom-Json).items.Count -ne 0)) {
        throw "Managed runtimes remain after acceptance"
    }
    $routeFiles = @(Get-ChildItem -LiteralPath $settings.M10_DOCKER_ROUTE_ROOT `
        -Filter "runtime-*.yml" -File -ErrorAction SilentlyContinue)
    if ($routeFiles.Count -ne 0) { throw "Dynamic runtime routes remain after acceptance" }
}

Write-Host "Milestone 14 automated public-boundary checks passed."
if (-not $RequireRomMUsers) { Write-Host "Rerun with -RequireRomMUsers after both users sign in." }
if (-not $RequireClean) { Write-Host "Rerun with -RequireClean after the host closes the accepted lobby." }
