[CmdletBinding()]
param(
    [string]$RomMSource = "<separate-romm-worktree>",
    [string]$RomPath = "local/test-roms/super-tilt-bro-2.6.nes",
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$romMRoot = (Resolve-Path -LiteralPath $RomMSource).Path
$resolvedRom = (Resolve-Path (Join-Path $repositoryRoot $RomPath)).Path
$composeFiles = @(
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone10.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone11.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone12.yml")
)
$environmentFile = Join-Path $repositoryRoot ".env.milestone12"
$stateRoot = Join-Path $repositoryRoot "local/runtime-agent-m12"
$libraryRoot = Join-Path $repositoryRoot "local/milestone12-library"
$romDirectory = Join-Path $libraryRoot "nes/roms"
$userDataRoot = Join-Path $stateRoot "userdata"
$routeRoot = Join-Path $stateRoot "routes"

function New-RandomHex([int]$Bytes) {
    return [Convert]::ToHexString(
        [Security.Cryptography.RandomNumberGenerator]::GetBytes($Bytes)
    ).ToLowerInvariant()
}

$preservedSettings = @{}
if (Test-Path -LiteralPath $environmentFile) {
    Get-Content -LiteralPath $environmentFile | ForEach-Object {
        if ($_ -match '^([^#=]+)=(.*)$') { $preservedSettings[$Matches[1]] = $Matches[2] }
    }
}

function Get-OrCreateSecret([string]$Name, [int]$Bytes) {
    $existing = $preservedSettings[$Name]
    if ($existing) { return $existing }
    return New-RandomHex $Bytes
}

if ((git -C $romMRoot branch --show-current) -ne "feat/external-multiplayer-provider") {
    throw "RomMSource must be on feat/external-multiplayer-provider"
}

foreach ($directory in @($libraryRoot, $romDirectory, $stateRoot, $userDataRoot, $routeRoot)) {
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
}
Copy-Item -LiteralPath (Join-Path $repositoryRoot "infra/traefik/dynamic/milestone12-romm.yml") `
    -Destination (Join-Path $routeRoot "romm.yml") -Force
Copy-Item -LiteralPath $resolvedRom -Destination $romDirectory -Force
$managedRom = Join-Path $romDirectory (Split-Path -Leaf $resolvedRom)

docker build --target slim-image --tag retrobrowser/romm:milestone12 `
    --file (Join-Path $romMRoot "docker/Dockerfile") $romMRoot
if ($LASTEXITCODE -ne 0) { throw "RomM image build failed" }
docker build --tag retrobrowser/retro-session:milestone12 `
    --file (Join-Path $repositoryRoot "images/retro-session/Dockerfile") $repositoryRoot
if ($LASTEXITCODE -ne 0) { throw "retro-session image build failed" }

$romMImageId = docker image inspect --format "{{.Id}}" retrobrowser/romm:milestone12
$runtimeImageId = docker image inspect --format "{{.Id}}" retrobrowser/retro-session:milestone12
if (-not $romMImageId.StartsWith("sha256:") -or -not $runtimeImageId.StartsWith("sha256:")) {
    throw "Could not resolve locally built image digests"
}

$romMUrl = "http://localhost:8096"
$authentikUrl = "http://auth.127.0.0.1.nip.io:9000"
$environment = @(
    "M10_RUNTIME_IMAGE=retrobrowser/retro-session@$runtimeImageId"
    "M10_DOCKER_ROM_ROOT=$libraryRoot"
    "M10_DOCKER_USER_DATA_ROOT=$userDataRoot"
    "M10_DOCKER_ROUTE_ROOT=$routeRoot"
    "M10_ROM_FILENAME=$(Split-Path -Leaf $managedRom)"
    "M10_ROM_SHA256=$((Get-FileHash -Algorithm SHA256 -LiteralPath $managedRom).Hash.ToLowerInvariant())"
    "M10_SERVICE_TOKEN=$(Get-OrCreateSecret 'M10_SERVICE_TOKEN' 32)"
    "M10_ORCHESTRATION_SECRET=$(Get-OrCreateSecret 'M10_ORCHESTRATION_SECRET' 32)"
    "M11_AUTHENTIK_SECRET_KEY=$(Get-OrCreateSecret 'M11_AUTHENTIK_SECRET_KEY' 60)"
    "M11_AUTHENTIK_POSTGRES_PASSWORD=$(Get-OrCreateSecret 'M11_AUTHENTIK_POSTGRES_PASSWORD' 32)"
    "M11_BOOTSTRAP_TOKEN=$(Get-OrCreateSecret 'M11_BOOTSTRAP_TOKEN' 32)"
    "M11_ADMIN_EMAIL=admin@retrobrowser.test"
    "M11_ADMIN_PASSWORD=$(Get-OrCreateSecret 'M11_ADMIN_PASSWORD' 20)"
    "M11_SMTP_FROM=Retro Browser <noreply@retrobrowser.test>"
    "M11_OIDC_CLIENT_ID=retrobrowser-romm"
    "M11_OIDC_CLIENT_SECRET=$(Get-OrCreateSecret 'M11_OIDC_CLIENT_SECRET' 32)"
    "M11_AUTHENTIK_URL=$authentikUrl"
    "M11_ROMM_URL=$romMUrl"
    "M11_ROMM_DB_PASSWORD=$(Get-OrCreateSecret 'M11_ROMM_DB_PASSWORD' 32)"
    "M11_ROMM_DB_ROOT_PASSWORD=$(Get-OrCreateSecret 'M11_ROMM_DB_ROOT_PASSWORD' 32)"
    "M11_ROMM_AUTH_SECRET_KEY=$(Get-OrCreateSecret 'M11_ROMM_AUTH_SECRET_KEY' 32)"
    "M11_TEST_USER_A_EMAIL=player-one@retrobrowser.test"
    "M11_TEST_USER_B_EMAIL=player-two@retrobrowser.test"
    "M12_ROMM_IMAGE=retrobrowser/romm@$romMImageId"
    "M12_ROMM_URL=$romMUrl"
)
$environment | Set-Content -LiteralPath $environmentFile -Encoding utf8NoBOM

$arguments = @("compose", "--env-file", $environmentFile)
foreach ($file in $composeFiles) { $arguments += @("--file", $file) }
docker @arguments up --detach --build
if ($LASTEXITCODE -ne 0) { throw "Milestone 12 stack start failed" }

$settings = @{}
Get-Content -LiteralPath $environmentFile | ForEach-Object {
    if ($_ -match '^([^#=]+)=(.*)$') { $settings[$Matches[1]] = $Matches[2] }
}
$headers = @{ Authorization = "Bearer $($settings.M11_BOOTSTRAP_TOKEN)" }
$deadline = (Get-Date).AddMinutes(6)
do {
    try {
        $null = Invoke-RestMethod -Uri "http://127.0.0.1:9000/-/health/ready/" `
            -TimeoutSec 5
        $authentikReady = $true
    } catch {
        $authentikReady = $false
        Start-Sleep -Seconds 3
    }
} while (-not $authentikReady -and (Get-Date) -lt $deadline)
if (-not $authentikReady) { throw "authentik did not become ready" }

foreach ($user in @(
    @{ username = "player-one"; name = "Player One"; email = $settings.M11_TEST_USER_A_EMAIL },
    @{ username = "player-two"; name = "Player Two"; email = $settings.M11_TEST_USER_B_EMAIL }
)) {
    $encodedUsername = [Uri]::EscapeDataString($user.username)
    $existing = Invoke-RestMethod `
        -Uri "http://127.0.0.1:9000/api/v3/core/users/?username=$encodedUsername" `
        -Headers $headers -TimeoutSec 10
    if ($existing.pagination.count -eq 0) {
        $body = @{
            username = $user.username
            name = $user.name
            email = $user.email
            is_active = $true
            attributes = @{ email_verified = $true }
        } | ConvertTo-Json -Depth 4
        $null = Invoke-RestMethod -Method Post `
            -Uri "http://127.0.0.1:9000/api/v3/core/users/" -Headers $headers `
            -ContentType "application/json" -Body $body -TimeoutSec 10
    }
}

$providerName = [Uri]::EscapeDataString("Retro Browser RomM OIDC")
$deadline = (Get-Date).AddMinutes(2)
do {
    $provider = Invoke-RestMethod `
        -Uri "http://127.0.0.1:9000/api/v3/providers/oauth2/?name=$providerName" `
        -Headers $headers -TimeoutSec 10
    if ($provider.pagination.count -ne 1) { Start-Sleep -Seconds 2 }
} while ($provider.pagination.count -ne 1 -and (Get-Date) -lt $deadline)
if ($provider.pagination.count -ne 1) {
    throw "The RomM OIDC provider was not provisioned"
}
$callbackUrl = "$romMUrl/api/oauth/openid"
$redirect = $provider.results[0].redirect_uris
if ($redirect.Count -ne 1 -or $redirect[0].matching_mode -ne "strict" -or
    $redirect[0].url -ne $callbackUrl) {
    $body = @{
        redirect_uris = @(@{
            matching_mode = "strict"
            url = $callbackUrl
            redirect_uri_type = "authorization"
        })
    } | ConvertTo-Json -Depth 4
    $null = Invoke-RestMethod -Method Patch `
        -Uri "http://127.0.0.1:9000/api/v3/providers/oauth2/$($provider.results[0].pk)/" `
        -Headers $headers -ContentType "application/json" -Body $body -TimeoutSec 10
}

$deadline = (Get-Date).AddMinutes(8)
do {
    try {
        $heartbeat = Invoke-WebRequest -Uri "$romMUrl/api/heartbeat" -TimeoutSec 5
        $ready = $heartbeat.StatusCode -eq 200
    } catch {
        $ready = $false
        Start-Sleep -Seconds 3
    }
} while (-not $ready -and (Get-Date) -lt $deadline)
if (-not $ready) { throw "Milestone 12 did not become ready" }

Write-Host "Milestone 12 is ready at $romMUrl"
Write-Host "Scan the NES platform in RomM, open the imported game, and use Multiplayer sessions."
Write-Host "Test-user addresses and local authentik bootstrap credentials are in .env.milestone12."
Write-Host "Open Mailpit at http://127.0.0.1:8025 and use separate private browser profiles."
if (-not $NoBrowser) { Start-Process "$romMUrl/login" }
