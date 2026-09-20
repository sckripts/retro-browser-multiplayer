[CmdletBinding()]
param(
    [switch]$CpuFallback,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$envFile = Join-Path $repoRoot ".env.milestone5"
$composeFile = Join-Path $repoRoot "infra/compose/acceptance/compose.milestone5.yml"
$gpuFile = Join-Path $repoRoot "infra/compose/acceptance/compose.milestone5.gpu.yml"
$defaultRomPath = Join-Path $repoRoot "local/test-roms/super-tilt-bro-2.6.nes"
$expectedRomSha256 = "847155bb712e474f71554174c9d9ed402bf651b13ff1e4afc9a42ec69cd03d8d"

function New-HexToken {
    $bytes = [byte[]]::new(32)
    [Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return [Convert]::ToHexString($bytes).ToLowerInvariant()
}

if (-not (Test-Path -LiteralPath $envFile)) {
    @(
        "M5_HOST_MASTER_TOKEN=$(New-HexToken)"
        "M5_HOST_SESSION_TOKEN=$(New-HexToken)"
        "M5_CLIENT_MASTER_TOKEN=$(New-HexToken)"
        "M5_CLIENT_SESSION_TOKEN=$(New-HexToken)"
        "M5_BIND_ADDRESS=0.0.0.0"
        "M5_HTTP_PORT=8090"
        "M5_ALLOWED_ORIGINS="
        "M5_ROM_PATH=$defaultRomPath"
    ) | Set-Content -LiteralPath $envFile -Encoding utf8NoBOM
    Write-Host "Created ignored Milestone 5 credentials and ROM path."
}

$settings = @{}
foreach ($line in Get-Content -LiteralPath $envFile) {
    if ($line -match '^s*([^#=]+)=(.*)$') {
        $settings[$matches[1].Trim()] = $matches[2]
    }
}

foreach ($required in @(
    "M5_HOST_MASTER_TOKEN",
    "M5_HOST_SESSION_TOKEN",
    "M5_CLIENT_MASTER_TOKEN",
    "M5_CLIENT_SESSION_TOKEN",
    "M5_HTTP_PORT",
    "M5_ROM_PATH"
)) {
    if ([string]::IsNullOrWhiteSpace($settings[$required])) {
        throw "$required is missing from $envFile"
    }
}

$romPath = [IO.Path]::GetFullPath($settings["M5_ROM_PATH"])
if (-not (Test-Path -LiteralPath $romPath -PathType Leaf)) {
    throw "The legal test ROM is missing. Run .\tools\test-roms\fetch-super-tilt-bro.ps1 first."
}
$actualRomSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $romPath).Hash.ToLowerInvariant()
if ($actualRomSha256 -ne $expectedRomSha256) {
    throw "The configured ROM has an unexpected SHA-256: $actualRomSha256"
}

$composeBaseArgs = @("compose", "--env-file", $envFile, "-f", $composeFile)
if (-not $CpuFallback) {
    $composeBaseArgs += @("-f", $gpuFile)
}

& docker @($composeBaseArgs + @("up", "-d", "--build", "--wait"))
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose failed with exit code $LASTEXITCODE"
}

& docker @($composeBaseArgs + @(
    "up", "-d", "--no-deps", "--force-recreate", "--wait", "edge"
))
if ($LASTEXITCODE -ne 0) {
    throw "Traefik refresh failed with exit code $LASTEXITCODE"
}

$rootUri = "http://127.0.0.1:$($settings['M5_HTTP_PORT'])"
$hostBaseUri = "$rootUri/stream/m5-host"
$clientBaseUri = "$rootUri/stream/m5-client"
$hostTokenBody = @{
    $settings["M5_HOST_SESSION_TOKEN"] = @{
        role = "controller"
        slot = 1
    }
} | ConvertTo-Json -Depth 4 -Compress
$clientTokenBody = @{
    $settings["M5_CLIENT_SESSION_TOKEN"] = @{
        role = "controller"
        slot = 1
    }
} | ConvertTo-Json -Depth 4 -Compress

Invoke-RestMethod -Method Post -Uri "$hostBaseUri/api/tokens" -Headers @{
    Authorization = "Bearer $($settings['M5_HOST_MASTER_TOKEN'])"
} -ContentType "application/json" -Body $hostTokenBody | Out-Null
Invoke-RestMethod -Method Post -Uri "$clientBaseUri/api/tokens" -Headers @{
    Authorization = "Bearer $($settings['M5_CLIENT_MASTER_TOKEN'])"
} -ContentType "application/json" -Body $clientTokenBody | Out-Null

if (-not $NoBrowser) {
    $hostLaunchUri = "$hostBaseUri/?token=$($settings['M5_HOST_SESSION_TOKEN'])"
    $clientLaunchUri = "$clientBaseUri/?token=$($settings['M5_CLIENT_SESSION_TOKEN'])"
    Start-Process "msedge.exe" -ArgumentList "--new-window", $hostLaunchUri
    Start-Process "msedge.exe" -ArgumentList "--inprivate", "--new-window", $clientLaunchUri
}

$encoder = if ($CpuFallback) { "forced x264 software H.264" } else { "NVIDIA attempt with x264 fallback" }
Write-Host "Milestone 5 host is healthy at $hostBaseUri/."
Write-Host "Milestone 5 client is healthy at $clientBaseUri/."
Write-Host "Both verified runtimes use private TCP Netplay ($encoder)."
Write-Host "Controller tokens were issued but were not printed."
