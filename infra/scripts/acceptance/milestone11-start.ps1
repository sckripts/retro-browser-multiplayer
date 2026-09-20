[CmdletBinding()]
param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$composeFile = Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone11.yml"
$environmentFile = Join-Path $repositoryRoot ".env.milestone11"

function New-RandomHex([int]$Bytes) {
    return [Convert]::ToHexString(
        [Security.Cryptography.RandomNumberGenerator]::GetBytes($Bytes)
    ).ToLowerInvariant()
}

if (-not (Test-Path -LiteralPath $environmentFile)) {
    $environment = @(
        "M11_AUTHENTIK_SECRET_KEY=$(New-RandomHex 60)"
        "M11_AUTHENTIK_POSTGRES_PASSWORD=$(New-RandomHex 32)"
        "M11_BOOTSTRAP_TOKEN=$(New-RandomHex 32)"
        "M11_ADMIN_EMAIL=admin@retrobrowser.test"
        "M11_ADMIN_PASSWORD=$(New-RandomHex 20)"
        "M11_SMTP_FROM=Retro Browser <noreply@retrobrowser.test>"
        "M11_OIDC_CLIENT_ID=retrobrowser-romm"
        "M11_OIDC_CLIENT_SECRET=$(New-RandomHex 32)"
        "M11_AUTHENTIK_URL=http://auth.127.0.0.1.nip.io:9000"
        "M11_ROMM_URL=http://romm.127.0.0.1.nip.io:8095"
        "M11_ROMM_DB_PASSWORD=$(New-RandomHex 32)"
        "M11_ROMM_DB_ROOT_PASSWORD=$(New-RandomHex 32)"
        "M11_ROMM_AUTH_SECRET_KEY=$(New-RandomHex 32)"
        "M11_TEST_USER_A_EMAIL=player-one@retrobrowser.test"
        "M11_TEST_USER_B_EMAIL=player-two@retrobrowser.test"
    )
    $environment | Set-Content -LiteralPath $environmentFile -Encoding utf8NoBOM
    Write-Host "Created ignored Milestone 11 credentials at .env.milestone11."
}

docker compose --env-file $environmentFile --file $composeFile up --detach
if ($LASTEXITCODE -ne 0) { throw "Milestone 11 stack start failed" }

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
        $ready = $true
    } catch {
        $ready = $false
        Start-Sleep -Seconds 3
    }
} while (-not $ready -and (Get-Date) -lt $deadline)
if (-not $ready) { throw "authentik did not become ready" }

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

$deadline = (Get-Date).AddMinutes(6)
do {
    try {
        $discovery = Invoke-RestMethod `
            -Uri "http://auth.127.0.0.1.nip.io:9000/application/o/romm/.well-known/openid-configuration" `
            -TimeoutSec 5
        $romm = Invoke-WebRequest -Uri "http://romm.127.0.0.1.nip.io:8095/api/heartbeat" `
            -TimeoutSec 5
        $stackReady = $discovery.issuer -and $romm.StatusCode -eq 200
    } catch {
        $stackReady = $false
        Start-Sleep -Seconds 3
    }
} while (-not $stackReady -and (Get-Date) -lt $deadline)
if (-not $stackReady) { throw "RomM or the RomM OIDC provider did not become ready" }

Write-Host "Milestone 11 is ready:"
Write-Host "  RomM:      http://romm.127.0.0.1.nip.io:8095"
Write-Host "  authentik: http://auth.127.0.0.1.nip.io:9000"
Write-Host "  Mailpit:   http://127.0.0.1:8025"
Write-Host "Test-user addresses and the emergency akadmin credential are in .env.milestone11."
Write-Host "Use separate private browser windows for the two email-link sign-ins."
if (-not $NoBrowser) {
    Start-Process "http://romm.127.0.0.1.nip.io:8095/login"
    Start-Process "http://127.0.0.1:8025"
}
