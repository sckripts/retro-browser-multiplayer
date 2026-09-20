[CmdletBinding()]
param(
    [string]$RomMSource = "<separate-romm-worktree>",
    [string]$RomPath = "local/test-roms/super-tilt-bro-2.6.nes",
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$romMRoot = (Resolve-Path -LiteralPath $RomMSource).Path
$environmentFile = Join-Path $repositoryRoot ".env.milestone14"
$m12EnvironmentFile = Join-Path $repositoryRoot ".env.milestone12"
$m3EnvironmentFile = Join-Path $repositoryRoot ".env.milestone3"
$stateRoot = Join-Path $repositoryRoot "local/runtime-agent-m14"
$libraryRoot = Join-Path $repositoryRoot "local/milestone14-library"
$romDirectory = Join-Path $libraryRoot "nes/roms"
$userDataRoot = Join-Path $stateRoot "userdata"
$routeRoot = Join-Path $stateRoot "routes"
$templateFile = Join-Path $repositoryRoot "infra/traefik/dynamic/milestone14-base.template.yml"
$composeFiles = @(
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone10.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone11.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone12.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone14.yml")
)

function Read-EnvSettings([string]$Path) {
    $result = @{}
    if (Test-Path -LiteralPath $Path) {
        Get-Content -LiteralPath $Path | ForEach-Object {
            if ($_ -match '^\s*([^#=]+)=(.*)$') {
                $value = $Matches[2].Trim()
                if ($value.Length -ge 2 -and
                    (($value.StartsWith("'") -and $value.EndsWith("'")) -or
                    ($value.StartsWith('"') -and $value.EndsWith('"')))) {
                    $value = $value.Substring(1, $value.Length - 2)
                }
                $result[$Matches[1].Trim()] = $value
            }
        }
    }
    return $result
}

function New-HexToken([int]$Bytes) {
    return [Convert]::ToHexString(
        [Security.Cryptography.RandomNumberGenerator]::GetBytes($Bytes)
    ).ToLowerInvariant()
}

if (-not (Test-Path -LiteralPath $environmentFile)) {
    $m12 = Read-EnvSettings $m12EnvironmentFile
    $m3 = Read-EnvSettings $m3EnvironmentFile
    @(
        "M10_RUNTIME_IMAGE="
        "M10_DOCKER_ROM_ROOT=$libraryRoot"
        "M10_DOCKER_USER_DATA_ROOT=$userDataRoot"
        "M10_DOCKER_ROUTE_ROOT=$routeRoot"
        "M10_ROM_FILENAME="
        "M10_ROM_SHA256="
        "M10_SERVICE_TOKEN=$(if ($m12.M10_SERVICE_TOKEN) { $m12.M10_SERVICE_TOKEN } else { New-HexToken 32 })"
        "M10_ORCHESTRATION_SECRET=$(if ($m12.M10_ORCHESTRATION_SECRET) { $m12.M10_ORCHESTRATION_SECRET } else { New-HexToken 32 })"
        "M11_AUTHENTIK_SECRET_KEY=$(if ($m12.M11_AUTHENTIK_SECRET_KEY) { $m12.M11_AUTHENTIK_SECRET_KEY } else { New-HexToken 60 })"
        "M11_AUTHENTIK_POSTGRES_PASSWORD=$(if ($m12.M11_AUTHENTIK_POSTGRES_PASSWORD) { $m12.M11_AUTHENTIK_POSTGRES_PASSWORD } else { New-HexToken 32 })"
        "M11_BOOTSTRAP_TOKEN=$(if ($m12.M11_BOOTSTRAP_TOKEN) { $m12.M11_BOOTSTRAP_TOKEN } else { New-HexToken 32 })"
        "M11_ADMIN_EMAIL="
        "M11_ADMIN_PASSWORD=$(if ($m12.M11_ADMIN_PASSWORD) { $m12.M11_ADMIN_PASSWORD } else { New-HexToken 20 })"
        "M11_SMTP_FROM="
        "M11_OIDC_CLIENT_ID=retrobrowser-romm"
        "M11_OIDC_CLIENT_SECRET=$(if ($m12.M11_OIDC_CLIENT_SECRET) { $m12.M11_OIDC_CLIENT_SECRET } else { New-HexToken 32 })"
        "M11_AUTHENTIK_URL="
        "M11_ROMM_URL="
        "M11_ROMM_DB_PASSWORD=$(if ($m12.M11_ROMM_DB_PASSWORD) { $m12.M11_ROMM_DB_PASSWORD } else { New-HexToken 32 })"
        "M11_ROMM_DB_ROOT_PASSWORD=$(if ($m12.M11_ROMM_DB_ROOT_PASSWORD) { $m12.M11_ROMM_DB_ROOT_PASSWORD } else { New-HexToken 32 })"
        "M11_ROMM_AUTH_SECRET_KEY=$(if ($m12.M11_ROMM_AUTH_SECRET_KEY) { $m12.M11_ROMM_AUTH_SECRET_KEY } else { New-HexToken 32 })"
        "M11_TEST_USER_A_EMAIL="
        "M11_TEST_USER_B_EMAIL="
        "M12_ROMM_IMAGE="
        "M12_ROMM_URL="
        "M14_ROMM_IMAGE="
        "M14_PUBLIC_HOSTNAME=$($m3.M3_PUBLIC_HOSTNAME)"
        "M14_AUTH_HOSTNAME="
        "M14_TURN_HOST=$($m3.M3_TURN_HOST)"
        "M14_TURN_REALM=$(if ($m3.M3_TURN_REALM) { $m3.M3_TURN_REALM } else { $m3.M3_TURN_HOST })"
        "M14_TLS_CERT_FILE=$($m3.M3_TLS_CERT_FILE)"
        "M14_TLS_KEY_FILE=$($m3.M3_TLS_KEY_FILE)"
        "M14_TURN_SHARED_SECRET=$(New-HexToken 32)"
        "M14_TURN_REST_API_KEY=$(New-HexToken 32)"
        "M14_SMTP_HOST="
        "M14_SMTP_PORT=587"
        "M14_SMTP_USERNAME="
        "M14_SMTP_PASSWORD="
        "M14_SMTP_USE_TLS=true"
        "M14_SMTP_USE_SSL=false"
        "M14_SMTP_FROM="
        "M14_BIND_ADDRESS=0.0.0.0"
        "M14_HTTP_PORT=80"
        "M14_HTTPS_PORT=443"
        "M14_TURN_PORT=3478"
        "M14_TURN_TLS_PORT=5349"
    ) | Set-Content -LiteralPath $environmentFile -Encoding utf8NoBOM
    Write-Host "Created ignored .env.milestone14 with generated platform and TURN secrets."
    Write-Host "Set the auth hostname, certificate, SMTP, administrator, and two real test-user email values, then run this command again."
    exit 2
}

$settings = Read-EnvSettings $environmentFile
$required = @(
    "M10_SERVICE_TOKEN", "M10_ORCHESTRATION_SECRET", "M11_AUTHENTIK_SECRET_KEY",
    "M11_AUTHENTIK_POSTGRES_PASSWORD", "M11_BOOTSTRAP_TOKEN", "M11_ADMIN_EMAIL",
    "M11_ADMIN_PASSWORD", "M11_OIDC_CLIENT_ID", "M11_OIDC_CLIENT_SECRET",
    "M11_ROMM_DB_PASSWORD", "M11_ROMM_DB_ROOT_PASSWORD", "M11_ROMM_AUTH_SECRET_KEY",
    "M11_TEST_USER_A_EMAIL", "M11_TEST_USER_B_EMAIL", "M14_PUBLIC_HOSTNAME",
    "M14_AUTH_HOSTNAME", "M14_TURN_HOST", "M14_TURN_REALM", "M14_TLS_CERT_FILE",
    "M14_TLS_KEY_FILE", "M14_TURN_SHARED_SECRET", "M14_TURN_REST_API_KEY",
    "M14_SMTP_HOST", "M14_SMTP_PORT", "M14_SMTP_USERNAME", "M14_SMTP_PASSWORD",
    "M14_SMTP_FROM"
)
foreach ($name in $required) {
    if ([string]::IsNullOrWhiteSpace($settings[$name])) { throw "$name is missing from $environmentFile" }
}

$hostnamePattern = '^(?=.{1,253}$)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])$'
$publicHostname = $settings.M14_PUBLIC_HOSTNAME.Trim().ToLowerInvariant()
$authHostname = $settings.M14_AUTH_HOSTNAME.Trim().ToLowerInvariant()
$turnHostname = $settings.M14_TURN_HOST.Trim().ToLowerInvariant()
foreach ($candidate in @($publicHostname, $authHostname, $turnHostname)) {
    $parsedAddress = $null
    if ($candidate -notmatch $hostnamePattern -or $candidate -notmatch '\.' -or
        [Net.IPAddress]::TryParse($candidate, [ref]$parsedAddress)) {
        throw "Milestone 14 requires public DNS hostnames, not localhost or an IP: $candidate"
    }
}
if ($publicHostname -eq $authHostname) { throw "RomM and authentik require distinct hostnames" }
if ($settings.M11_TEST_USER_A_EMAIL -eq $settings.M11_TEST_USER_B_EMAIL) {
    throw "Milestone 14 requires two distinct user email addresses"
}
foreach ($booleanName in @("M14_SMTP_USE_TLS", "M14_SMTP_USE_SSL")) {
    if ($settings[$booleanName] -notin @("true", "false")) { throw "$booleanName must be true or false" }
}
if ($settings.M14_SMTP_USE_TLS -eq "true" -and $settings.M14_SMTP_USE_SSL -eq "true") {
    throw "Enable SMTP STARTTLS or implicit SSL, not both"
}

$certificatePath = [IO.Path]::GetFullPath($settings.M14_TLS_CERT_FILE)
$privateKeyPath = [IO.Path]::GetFullPath($settings.M14_TLS_KEY_FILE)
foreach ($path in @($certificatePath, $privateKeyPath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "TLS file does not exist: $path" }
}
$certificate = [Security.Cryptography.X509Certificates.X509Certificate2]::CreateFromPemFile(
    $certificatePath, $privateKeyPath
)
try {
    $now = [DateTimeOffset]::Now
    if ($now -lt $certificate.NotBefore -or $now -gt $certificate.NotAfter) {
        throw "The configured TLS certificate is not currently valid"
    }
    foreach ($tlsHostname in @($publicHostname, $authHostname, $turnHostname) | Select-Object -Unique) {
        if (-not $certificate.MatchesHostname($tlsHostname)) {
            throw "The configured TLS certificate does not match $tlsHostname"
        }
    }
}
finally { $certificate.Dispose() }

if ((git -C $romMRoot branch --show-current) -ne "feat/external-multiplayer-provider") {
    throw "RomMSource must be on feat/external-multiplayer-provider"
}
$resolvedRom = (Resolve-Path (Join-Path $repositoryRoot $RomPath)).Path
foreach ($directory in @($libraryRoot, $romDirectory, $stateRoot, $userDataRoot, $routeRoot)) {
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
}
$managedRom = Join-Path $romDirectory (Split-Path -Leaf $resolvedRom)
Copy-Item -LiteralPath $resolvedRom -Destination $managedRom -Force
$baseRoute = (Get-Content -LiteralPath $templateFile -Raw).
    Replace("__M14_PUBLIC_HOSTNAME__", $publicHostname).
    Replace("__M14_AUTH_HOSTNAME__", $authHostname)
Set-Content -LiteralPath (Join-Path $routeRoot "milestone14-base.yml") -Value $baseRoute -Encoding utf8NoBOM

docker build --target slim-image --tag retrobrowser/romm:milestone14 `
    --file (Join-Path $romMRoot "docker/Dockerfile") $romMRoot
if ($LASTEXITCODE -ne 0) { throw "RomM image build failed" }
docker build --tag retrobrowser/retro-session:milestone14 `
    --file (Join-Path $repositoryRoot "images/retro-session/Dockerfile") $repositoryRoot
if ($LASTEXITCODE -ne 0) { throw "retro-session image build failed" }
$romMImageId = docker image inspect --format "{{.Id}}" retrobrowser/romm:milestone14
$runtimeImageId = docker image inspect --format "{{.Id}}" retrobrowser/retro-session:milestone14
if (-not $romMImageId.StartsWith("sha256:") -or -not $runtimeImageId.StartsWith("sha256:")) {
    throw "Could not resolve locally built image digests"
}

$updates = @{
    M10_RUNTIME_IMAGE = "retrobrowser/retro-session@$runtimeImageId"
    M10_DOCKER_ROM_ROOT = $libraryRoot
    M10_DOCKER_USER_DATA_ROOT = $userDataRoot
    M10_DOCKER_ROUTE_ROOT = $routeRoot
    M10_ROM_FILENAME = (Split-Path -Leaf $managedRom)
    M10_ROM_SHA256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $managedRom).Hash.ToLowerInvariant()
    M11_AUTHENTIK_URL = "https://$authHostname"
    M11_ROMM_URL = "https://$publicHostname"
    M11_SMTP_FROM = $settings.M14_SMTP_FROM
    M12_ROMM_IMAGE = "retrobrowser/romm@$romMImageId"
    M12_ROMM_URL = "https://$publicHostname"
    M14_ROMM_IMAGE = "retrobrowser/romm@$romMImageId"
}
$lines = [Collections.Generic.List[string]](Get-Content -LiteralPath $environmentFile)
foreach ($entry in $updates.GetEnumerator()) {
    $index = -1
    for ($position = 0; $position -lt $lines.Count; $position++) {
        if ($lines[$position] -match "^$([Regex]::Escape($entry.Key))=") { $index = $position; break }
    }
    $line = "$($entry.Key)=$($entry.Value)"
    if ($index -ge 0) { $lines[$index] = $line } else { $lines.Add($line) }
}
$lines | Set-Content -LiteralPath $environmentFile -Encoding utf8NoBOM

$composeArgs = @("compose", "--env-file", $environmentFile)
foreach ($file in $composeFiles) { $composeArgs += @("--file", $file) }
& docker @($composeArgs + @("up", "--detach", "--build", "--wait"))
if ($LASTEXITCODE -ne 0) { throw "Milestone 14 stack start failed" }

$settings = Read-EnvSettings $environmentFile
$headers = @{ Authorization = "Bearer $($settings.M11_BOOTSTRAP_TOKEN)" }
$authBase = "https://$authHostname"
foreach ($user in @(
    @{ username = "player-one"; name = "Player One"; email = $settings.M11_TEST_USER_A_EMAIL },
    @{ username = "player-two"; name = "Player Two"; email = $settings.M11_TEST_USER_B_EMAIL }
)) {
    $encodedUsername = [Uri]::EscapeDataString($user.username)
    $existing = Invoke-RestMethod -Uri "$authBase/api/v3/core/users/?username=$encodedUsername" `
        -Headers $headers -TimeoutSec 15
    if ($existing.pagination.count -eq 0) {
        $body = @{
            username = $user.username; name = $user.name; email = $user.email
            is_active = $true; attributes = @{ email_verified = $true }
        } | ConvertTo-Json -Depth 4
        $null = Invoke-RestMethod -Method Post -Uri "$authBase/api/v3/core/users/" `
            -Headers $headers -ContentType "application/json" -Body $body -TimeoutSec 15
    }
}

$provider = Invoke-RestMethod `
    -Uri "$authBase/api/v3/providers/oauth2/?name=Retro%20Arcade%20RomM%20OIDC" `
    -Headers $headers -TimeoutSec 15
$callbackUrl = "https://$publicHostname/api/oauth/openid"
if ($provider.pagination.count -ne 1) { throw "The RomM OIDC provider was not provisioned" }
$redirect = $provider.results[0].redirect_uris
if ($redirect.Count -ne 1 -or $redirect[0].matching_mode -ne "strict" -or
    $redirect[0].url -ne $callbackUrl) {
    $body = @{ redirect_uris = @(@{
        matching_mode = "strict"; url = $callbackUrl; redirect_uri_type = "authorization"
    }) } | ConvertTo-Json -Depth 4
    $null = Invoke-RestMethod -Method Patch `
        -Uri "$authBase/api/v3/providers/oauth2/$($provider.results[0].pk)/" `
        -Headers $headers -ContentType "application/json" -Body $body -TimeoutSec 15
}

Write-Host "Milestone 14 is ready at https://$publicHostname"
Write-Host "Run milestone14-verify.ps1, then perform the two-network acceptance checklist."
if (-not $NoBrowser) { Start-Process "https://$publicHostname/login" }
