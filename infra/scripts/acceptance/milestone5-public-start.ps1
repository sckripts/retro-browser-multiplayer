[CmdletBinding()]
param(
    [switch]$CpuFallback,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$envFile = Join-Path $repoRoot ".env.milestone5-public"
$m3EnvFile = Join-Path $repoRoot ".env.milestone3"
$composeFile = Join-Path $repoRoot "infra/compose/acceptance/compose.milestone5.public.yml"
$gpuFile = Join-Path $repoRoot "infra/compose/acceptance/compose.milestone5.gpu.yml"
$templateFile = Join-Path $repoRoot "infra/traefik/dynamic/milestone5-public.template.yml"
$generatedDirectory = Join-Path $repoRoot "infra/traefik/dynamic/generated"
$generatedFile = Join-Path $generatedDirectory "milestone5.yml"
$defaultRomPath = Join-Path $repoRoot "local/test-roms/super-tilt-bro-2.6.nes"
$expectedRomSha256 = "847155bb712e474f71554174c9d9ed402bf651b13ff1e4afc9a42ec69cd03d8d"

function New-HexToken {
    $bytes = [byte[]]::new(32)
    [Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return [Convert]::ToHexString($bytes).ToLowerInvariant()
}

function Read-EnvSettings([string]$Path) {
    $result = @{}
    if (Test-Path -LiteralPath $Path) {
        foreach ($line in Get-Content -LiteralPath $Path) {
            if ($line -match '^\s*([^#=]+)=(.*)$') {
                $result[$matches[1].Trim()] = $matches[2]
            }
        }
    }
    return $result
}

if (-not (Test-Path -LiteralPath $envFile)) {
    $previous = Read-EnvSettings $m3EnvFile
    @(
        "M5_HOST_MASTER_TOKEN=$(New-HexToken)"
        "M5_HOST_SESSION_TOKEN=$(New-HexToken)"
        "M5_CLIENT_MASTER_TOKEN=$(New-HexToken)"
        "M5_CLIENT_SESSION_TOKEN=$(New-HexToken)"
        "M5_TURN_SHARED_SECRET=$(New-HexToken)"
        "M5_TURN_REST_API_KEY=$(New-HexToken)"
        "M5_PUBLIC_HOSTNAME=$($previous['M3_PUBLIC_HOSTNAME'])"
        "M5_TURN_HOST=$($previous['M3_TURN_HOST'])"
        "M5_TURN_REALM=$($previous['M3_TURN_REALM'])"
        "M5_TLS_CERT_FILE=$($previous['M3_TLS_CERT_FILE'])"
        "M5_TLS_KEY_FILE=$($previous['M3_TLS_KEY_FILE'])"
        "M5_ROM_PATH=$(if ($previous['M3_ROM_PATH']) { $previous['M3_ROM_PATH'] } else { $defaultRomPath })"
        "M5_BIND_ADDRESS=0.0.0.0"
        "M5_HTTP_PORT=$(if ($previous['M3_HTTP_PORT']) { $previous['M3_HTTP_PORT'] } else { '80' })"
        "M5_HTTPS_PORT=$(if ($previous['M3_HTTPS_PORT']) { $previous['M3_HTTPS_PORT'] } else { '443' })"
        "M5_TURN_PORT=$(if ($previous['M3_TURN_PORT']) { $previous['M3_TURN_PORT'] } else { '3478' })"
        "M5_TURN_TLS_PORT=$(if ($previous['M3_TURN_TLS_PORT']) { $previous['M3_TURN_TLS_PORT'] } else { '5349' })"
    ) | Set-Content -LiteralPath $envFile -Encoding utf8NoBOM
    Write-Host "Created ignored Milestone 5 credentials and imported available Milestone 3 deployment settings."
}

$settings = Read-EnvSettings $envFile
$required = @(
    "M5_HOST_MASTER_TOKEN",
    "M5_HOST_SESSION_TOKEN",
    "M5_CLIENT_MASTER_TOKEN",
    "M5_CLIENT_SESSION_TOKEN",
    "M5_TURN_SHARED_SECRET",
    "M5_TURN_REST_API_KEY",
    "M5_PUBLIC_HOSTNAME",
    "M5_TURN_HOST",
    "M5_TURN_REALM",
    "M5_TLS_CERT_FILE",
    "M5_TLS_KEY_FILE",
    "M5_ROM_PATH",
    "M5_HTTPS_PORT"
)
foreach ($name in $required) {
    if ([string]::IsNullOrWhiteSpace($settings[$name])) {
        throw "$name is missing from $envFile"
    }
}

$hostname = $settings["M5_PUBLIC_HOSTNAME"].Trim().ToLowerInvariant()
$turnHostname = $settings["M5_TURN_HOST"].Trim().ToLowerInvariant()
$hostnamePattern = '^(?=.{1,253}$)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])$'
foreach ($candidate in @($hostname, $turnHostname)) {
    $parsedAddress = $null
    if (
        $candidate -notmatch $hostnamePattern -or
        $candidate -notmatch '\.' -or
        [Net.IPAddress]::TryParse($candidate, [ref]$parsedAddress)
    ) {
        throw "Milestone 5 requires DNS hostnames, not localhost or an IP address: $candidate"
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

$certificatePath = [IO.Path]::GetFullPath($settings["M5_TLS_CERT_FILE"])
$privateKeyPath = [IO.Path]::GetFullPath($settings["M5_TLS_KEY_FILE"])
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
    "__M5_PUBLIC_HOSTNAME__",
    $hostname
)
Set-Content -LiteralPath $generatedFile -Value $dynamicConfig -Encoding utf8NoBOM

$composeBaseArgs = @("compose", "--env-file", $envFile, "-f", $composeFile)
if (-not $CpuFallback) {
    $composeBaseArgs += @("-f", $gpuFile)
}

& docker @($composeBaseArgs + @("up", "-d", "--build", "--wait"))
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose failed with exit code $LASTEXITCODE"
}

& docker @($composeBaseArgs + @("up", "-d", "--no-deps", "--force-recreate", "--wait", "coturn", "edge"))
if ($LASTEXITCODE -ne 0) {
    throw "TLS service refresh failed with exit code $LASTEXITCODE"
}

$provisionCode = @'
import base64
import os
import sys
import urllib.request

body = base64.b64decode(sys.argv[2])
request = urllib.request.Request(
    f"http://127.0.0.1:8080{sys.argv[1]}/api/tokens",
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

function Convert-TokenBody([string]$Token) {
    $body = @{
        $Token = @{
            role = "controller"
            slot = 1
        }
    } | ConvertTo-Json -Depth 4 -Compress
    return [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($body))
}

$hostBody = Convert-TokenBody $settings["M5_HOST_SESSION_TOKEN"]
$clientBody = Convert-TokenBody $settings["M5_CLIENT_SESSION_TOKEN"]
& docker @($composeBaseArgs + @("exec", "-T", "retro-host", "python3", "-c", $provisionCode, "/stream/m5-host", $hostBody))
if ($LASTEXITCODE -ne 0) {
    throw "Host controller-token provisioning failed with exit code $LASTEXITCODE"
}
& docker @($composeBaseArgs + @("exec", "-T", "retro-client", "python3", "-c", $provisionCode, "/stream/m5-client", $clientBody))
if ($LASTEXITCODE -ne 0) {
    throw "Client controller-token provisioning failed with exit code $LASTEXITCODE"
}

$httpsPort = [int]$settings["M5_HTTPS_PORT"]
$authority = if ($httpsPort -eq 443) { $hostname } else { "${hostname}:$httpsPort" }
$hostBaseUri = "https://$authority/stream/m5-host"
$clientBaseUri = "https://$authority/stream/m5-client"
if (-not $NoBrowser) {
    Start-Process "$hostBaseUri/?token=$($settings['M5_HOST_SESSION_TOKEN'])"
    Start-Process "$clientBaseUri/?token=$($settings['M5_CLIENT_SESSION_TOKEN'])"
}

$encoder = if ($CpuFallback) { "forced x264 software H.264" } else { "NVIDIA attempt with x264 fallback" }
Write-Host "Milestone 5 public profile is healthy ($encoder)."
Write-Host "Host stream base: $hostBaseUri/"
Write-Host "Client stream base: $clientBaseUri/"
Write-Host "Controller tokens, TURN secret, and master tokens stayed server-side and were not printed."
