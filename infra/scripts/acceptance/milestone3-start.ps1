[CmdletBinding()]
param(
    [ValidateSet("direct", "turn-udp", "turn-tcp", "turn-tls")]
    [string]$Transport = "turn-udp",
    [switch]$CpuFallback,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$envFile = Join-Path $repoRoot ".env.milestone3"
$composeFile = Join-Path $repoRoot "infra/compose/acceptance/compose.public-test.yml"
$gpuFile = Join-Path $repoRoot "infra/compose/acceptance/compose.milestone3.gpu.yml"
$templateFile = Join-Path $repoRoot "infra/traefik/dynamic/milestone3.template.yml"
$generatedDirectory = Join-Path $repoRoot "infra/traefik/dynamic/generated"
$generatedFile = Join-Path $generatedDirectory "milestone3.yml"
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
    $turnSecret = New-HexToken
    $turnApiKey = New-HexToken
    @(
        "SELKIES_MASTER_TOKEN=$masterToken"
        "SELKIES_SESSION_TOKEN=$sessionToken"
        "M3_TURN_SHARED_SECRET=$turnSecret"
        "M3_TURN_REST_API_KEY=$turnApiKey"
        "M3_PUBLIC_HOSTNAME="
        "M3_TURN_HOST="
        "M3_TURN_REALM="
        "M3_TLS_CERT_FILE="
        "M3_TLS_KEY_FILE="
        "M3_ROM_PATH=$defaultRomPath"
        "M3_BIND_ADDRESS=0.0.0.0"
        "M3_HTTP_PORT=80"
        "M3_HTTPS_PORT=443"
        "M3_TURN_PORT=3478"
        "M3_TURN_TLS_PORT=5349"
    ) | Set-Content -LiteralPath $envFile -Encoding utf8NoBOM
    Write-Host "Created ignored Milestone 3 credentials and public deployment placeholders."
    Write-Host "Set the hostname and certificate paths in .env.milestone3, then run this command again."
    exit 2
}

$settings = @{}
foreach ($line in Get-Content -LiteralPath $envFile) {
    if ($line -match '^\s*([^#=]+)=(.*)$') {
        $settings[$matches[1].Trim()] = $matches[2]
    }
}

$required = @(
    "SELKIES_MASTER_TOKEN",
    "SELKIES_SESSION_TOKEN",
    "M3_TURN_SHARED_SECRET",
    "M3_TURN_REST_API_KEY",
    "M3_PUBLIC_HOSTNAME",
    "M3_TURN_HOST",
    "M3_TURN_REALM",
    "M3_TLS_CERT_FILE",
    "M3_TLS_KEY_FILE",
    "M3_ROM_PATH",
    "M3_HTTPS_PORT"
)
foreach ($name in $required) {
    if ([string]::IsNullOrWhiteSpace($settings[$name])) {
        throw "$name is missing from $envFile"
    }
}

$hostname = $settings["M3_PUBLIC_HOSTNAME"].Trim().ToLowerInvariant()
$turnHostname = $settings["M3_TURN_HOST"].Trim().ToLowerInvariant()
$hostnamePattern = '^(?=.{1,253}$)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])$'
foreach ($candidate in @($hostname, $turnHostname)) {
    $parsedAddress = $null
    if (
        $candidate -notmatch $hostnamePattern -or
        $candidate -notmatch '\.' -or
        [Net.IPAddress]::TryParse($candidate, [ref]$parsedAddress)
    ) {
        throw "Milestone 3 requires public DNS hostnames, not localhost or an IP address: $candidate"
    }
}

$romPath = [IO.Path]::GetFullPath($settings["M3_ROM_PATH"])
if (-not (Test-Path -LiteralPath $romPath -PathType Leaf)) {
    throw "The legal test ROM is missing. Run .\tools\test-roms\fetch-super-tilt-bro.ps1 first."
}
$actualRomSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $romPath).Hash.ToLowerInvariant()
if ($actualRomSha256 -ne $expectedRomSha256) {
    throw "The configured ROM has an unexpected SHA-256: $actualRomSha256"
}

$certificatePath = [IO.Path]::GetFullPath($settings["M3_TLS_CERT_FILE"])
$privateKeyPath = [IO.Path]::GetFullPath($settings["M3_TLS_KEY_FILE"])
foreach ($path in @($certificatePath, $privateKeyPath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "TLS file does not exist: $path"
    }
}
$certificate = [Security.Cryptography.X509Certificates.X509Certificate2]::CreateFromPemFile(
    $certificatePath,
    $privateKeyPath
)
try {
    $now = [DateTimeOffset]::Now
    if ($now -lt $certificate.NotBefore -or $now -gt $certificate.NotAfter) {
        throw "The configured TLS certificate is not currently valid."
    }
    foreach ($tlsHostname in @($hostname, $turnHostname) | Select-Object -Unique) {
        if (-not $certificate.MatchesHostname($tlsHostname)) {
            throw "The configured TLS certificate does not match $tlsHostname."
        }
    }
}
finally {
    $certificate.Dispose()
}

New-Item -ItemType Directory -Path $generatedDirectory -Force | Out-Null
$dynamicConfig = (Get-Content -LiteralPath $templateFile -Raw).Replace(
    "__M3_PUBLIC_HOSTNAME__",
    $hostname
)
Set-Content -LiteralPath $generatedFile -Value $dynamicConfig -Encoding utf8NoBOM

$composeBaseArgs = @("compose", "--env-file", $envFile, "-f", $composeFile)
switch ($Transport) {
    "direct" {
        $composeBaseArgs += @("-f", (Join-Path $repoRoot "infra/compose/acceptance/compose.milestone3.direct.yml"))
    }
    "turn-tcp" {
        $composeBaseArgs += @("-f", (Join-Path $repoRoot "infra/compose/acceptance/compose.milestone3.turn-tcp.yml"))
    }
    "turn-tls" {
        $composeBaseArgs += @("-f", (Join-Path $repoRoot "infra/compose/acceptance/compose.milestone3.turn-tls.yml"))
    }
    "turn-udp" {}
}
if (-not $CpuFallback) {
    $composeBaseArgs += @("-f", $gpuFile)
}

$composeArgs = $composeBaseArgs + @("up", "-d", "--build", "--wait")
& docker @composeArgs
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose failed with exit code $LASTEXITCODE"
}

$refreshArgs = $composeBaseArgs + @("up", "-d", "--no-deps", "--force-recreate", "--wait", "coturn", "edge")
& docker @refreshArgs
if ($LASTEXITCODE -ne 0) {
    throw "TLS service refresh failed with exit code $LASTEXITCODE"
}

$tokenBody = @{
    $settings["SELKIES_SESSION_TOKEN"] = @{
        role = "controller"
        slot = 1
    }
} | ConvertTo-Json -Depth 4 -Compress
$tokenBodyBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($tokenBody))
$provisionCode = @'
import base64
import json
import os
import sys
import urllib.request

body = base64.b64decode(sys.argv[1])
request = urllib.request.Request(
    "http://127.0.0.1:8080/stream/m3/api/tokens",
    data=body,
    headers={
        "Authorization": f"Bearer {os.environ['SELKIES_MASTER_TOKEN']}",
        "Content-Type": "application/json",
    },
    method="POST",
)
with urllib.request.urlopen(request, timeout=5):
    pass
'@
& docker @($composeBaseArgs + @("exec", "-T", "retro-session", "python3", "-c", $provisionCode, $tokenBodyBase64))
if ($LASTEXITCODE -ne 0) {
    throw "Scoped controller-token provisioning failed with exit code $LASTEXITCODE"
}

$httpsPort = [int]$settings["M3_HTTPS_PORT"]
$authority = if ($httpsPort -eq 443) { $hostname } else { "${hostname}:$httpsPort" }
$baseUri = "https://$authority/stream/m3"
if (-not $NoBrowser) {
    $launchUri = "$baseUri/?token=$($settings['SELKIES_SESSION_TOKEN'])"
    Start-Process $launchUri
}

$encoder = if ($CpuFallback) { "forced x264 software H.264" } else { "NVIDIA attempt with x264 fallback" }
Write-Host "Milestone 3 is healthy at $baseUri/ ($encoder, transport=$Transport)."
Write-Host "The TURN shared secret and master token stayed server-side and were not printed."
Write-Host "Confirm the selected ICE candidate pair in browser WebRTC diagnostics before acceptance."
