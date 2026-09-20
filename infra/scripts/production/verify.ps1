[CmdletBinding()]
param(
    [string]$EnvironmentFile = ".env.production",
    [switch]$RequireClean
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")
Assert-Command docker

$environmentPath = Get-ProductionEnvironmentPath $EnvironmentFile
if (-not (Test-Path -LiteralPath $environmentPath)) {
    throw "Production environment file not found: $environmentPath"
}
$settings = Read-ProductionSettings $environmentPath
$arguments = Get-ProductionComposeArguments $environmentPath
& docker @($arguments + @("config", "--quiet"))
if ($LASTEXITCODE -ne 0) {
    throw "Production Compose validation failed"
}

$expected = @(
    "authentik-postgres", "authentik-server", "authentik-worker", "coturn", "edge",
    "grafana", "prometheus", "romm", "romm-database", "runtime-agent",
    "session-manager", "turn-rest", "valkey"
)
$running = @(& docker @($arguments + @("ps", "--status", "running", "--services")))
if ($LASTEXITCODE -ne 0) {
    throw "Could not inspect production services"
}
$missing = @($expected | Where-Object { $_ -notin $running })
if ($missing) {
    throw "Production services are not running: $($missing -join ', ')"
}

& docker @($arguments + @("exec", "-T", "runtime-agent", "python", "-m", "retro_runtime.client", "health")) | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Runtime Agent health check failed"
}
$runtimeDocument = & docker @($arguments + @("exec", "-T", "runtime-agent", "python", "-m", "retro_runtime.client", "list"))
if ($LASTEXITCODE -ne 0) {
    throw "Runtime Agent inventory failed"
}
if ($RequireClean -and (($runtimeDocument | ConvertFrom-Json).items).Count -ne 0) {
    throw "Managed participant runtimes remain"
}

$response = Invoke-WebRequest -Uri "https://$($settings.PUBLIC_HOSTNAME)/api/heartbeat" -TimeoutSec 15
if ($response.StatusCode -ne 200) {
    throw "RomM heartbeat failed"
}
if (-not $response.Headers.'Content-Security-Policy-Report-Only' -or
    -not $response.Headers.'Permissions-Policy') {
    throw "Expected browser security headers are missing"
}

Write-Host "Production verification passed."
