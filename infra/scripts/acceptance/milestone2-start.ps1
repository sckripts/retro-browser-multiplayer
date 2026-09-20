[CmdletBinding()]
param(
    [switch]$CpuFallback,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$envFile = Join-Path $repoRoot ".env.milestone2"
$composeFile = Join-Path $repoRoot "infra/compose/acceptance/compose.milestone2.yml"
$gpuFile = Join-Path $repoRoot "infra/compose/acceptance/compose.milestone2.gpu.yml"
$defaultRomPath = Join-Path $repoRoot "local/test-roms/super-tilt-bro-2.6.nes"
$expectedRomSha256 = "847155bb712e474f71554174c9d9ed402bf651b13ff1e4afc9a42ec69cd03d8d"

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
        "M2_BIND_ADDRESS=127.0.0.1"
        "M2_HTTP_PORT=8089"
        "M2_ALLOWED_ORIGINS="
        "M2_ROM_PATH=$defaultRomPath"
    ) | Set-Content -LiteralPath $envFile -Encoding utf8NoBOM
    Write-Host "Created ignored local credentials and ROM path in .env.milestone2."
}

$settings = @{}
foreach ($line in Get-Content -LiteralPath $envFile) {
    if ($line -match '^\s*([^#=]+)=(.*)$') {
        $settings[$matches[1].Trim()] = $matches[2]
    }
}

foreach ($required in @(
    "SELKIES_MASTER_TOKEN",
    "SELKIES_SESSION_TOKEN",
    "M2_HTTP_PORT",
    "M2_ROM_PATH"
)) {
    if ([string]::IsNullOrWhiteSpace($settings[$required])) {
        throw "$required is missing from $envFile"
    }
}

$romPath = [IO.Path]::GetFullPath($settings["M2_ROM_PATH"])
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
$composeArgs = $composeBaseArgs + @("up", "-d", "--build", "--wait")

& docker @composeArgs
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose failed with exit code $LASTEXITCODE"
}

# Compose can recreate the runtime while retaining Traefik, whose existing
# process may still hold the prior container address. Recreate only the edge
# after the runtime is healthy so its backend lookup is always current.
$edgeArgs = $composeBaseArgs + @("up", "-d", "--no-deps", "--force-recreate", "--wait", "edge")
& docker @edgeArgs
if ($LASTEXITCODE -ne 0) {
    throw "Traefik refresh failed with exit code $LASTEXITCODE"
}

$baseUri = "http://127.0.0.1:$($settings['M2_HTTP_PORT'])/stream/m2"
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

$encoder = if ($CpuFallback) { "forced x264 software H.264" } else { "NVIDIA attempt with x264 fallback" }
Write-Host "Milestone 2 is healthy at $baseUri/ ($encoder)."
Write-Host "RetroArch launched the verified ROM directly; no desktop interaction is required."
Write-Host "The master token was not sent to the browser or printed."
