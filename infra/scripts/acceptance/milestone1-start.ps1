[CmdletBinding()]
param(
    [switch]$CpuFallback,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$envFile = Join-Path $repoRoot ".env.milestone1"
$composeFile = Join-Path $repoRoot "infra/compose/acceptance/compose.milestone1.yml"
$gpuFile = Join-Path $repoRoot "infra/compose/acceptance/compose.milestone1.gpu.yml"

function New-HexToken {
    $bytes = [byte[]]::new(32)
    [Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return [Convert]::ToHexString($bytes).ToLowerInvariant()
}

if (-not (Test-Path -LiteralPath $envFile)) {
    $masterToken = New-HexToken
    $sessionToken = New-HexToken
    @(
        "SELKIES_MASTER_TOKEN=$masterToken"
        "SELKIES_SESSION_TOKEN=$sessionToken"
        "M1_BIND_ADDRESS=127.0.0.1"
        "M1_HTTP_PORT=8088"
        "M1_ALLOWED_ORIGINS="
    ) | Set-Content -LiteralPath $envFile -Encoding utf8NoBOM
    Write-Host "Created ignored local credentials in .env.milestone1."
}

$settings = @{}
foreach ($line in Get-Content -LiteralPath $envFile) {
    if ($line -match '^\s*([^#=]+)=(.*)$') {
        $settings[$matches[1].Trim()] = $matches[2]
    }
}

foreach ($required in @("SELKIES_MASTER_TOKEN", "SELKIES_SESSION_TOKEN", "M1_HTTP_PORT")) {
    if ([string]::IsNullOrWhiteSpace($settings[$required])) {
        throw "$required is missing from $envFile"
    }
}

$composeArgs = @("compose", "--env-file", $envFile, "-f", $composeFile)
if (-not $CpuFallback) {
    $composeArgs += @("-f", $gpuFile)
}
$composeArgs += @("up", "-d", "--wait")

& docker @composeArgs
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose failed with exit code $LASTEXITCODE"
}

$baseUri = "http://127.0.0.1:$($settings['M1_HTTP_PORT'])/stream/m1"
$tokenBody = @{
    $settings["SELKIES_SESSION_TOKEN"] = @{
        role = "controller"
        slot = 1
    }
} | ConvertTo-Json -Depth 4 -Compress

Invoke-RestMethod `
    -Method Post `
    -Uri "$baseUri/api/tokens" `
    -Headers @{ Authorization = "Bearer $($settings['SELKIES_MASTER_TOKEN'])" } `
    -ContentType "application/json" `
    -Body $tokenBody | Out-Null

if (-not $NoBrowser) {
    $launchUri = "$baseUri/?token=$($settings['SELKIES_SESSION_TOKEN'])"
    Start-Process $launchUri
}

$encoder = if ($CpuFallback) { "forced software H.264" } else { "NVIDIA attempt with automatic software fallback" }
Write-Host "Milestone 1 is healthy and provisioned at $baseUri/ ($encoder)."
Write-Host "The master token was not sent to the browser or printed."
