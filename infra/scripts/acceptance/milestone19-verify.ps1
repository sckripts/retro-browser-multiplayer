[CmdletBinding()]
param(
    [switch]$RequireRomMUsers,
    [switch]$RequireClean
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$environmentFile = Join-Path $repositoryRoot ".env.milestone14"
if (-not (Test-Path -LiteralPath $environmentFile)) { throw "Run milestone19-start.ps1 first" }

& (Join-Path $PSScriptRoot "milestone18-verify.ps1") `
    -RequireRomMUsers:$RequireRomMUsers -RequireClean:$RequireClean
if ($LASTEXITCODE -ne 0) { throw "Milestone 18 verification failed" }

$composeFiles = @(
    "compose.milestone10.yml", "compose.milestone11.yml", "compose.milestone12.yml",
    "compose.milestone14.yml", "compose.milestone15.yml", "compose.milestone16.yml",
    "compose.milestone17.yml", "compose.milestone18.yml", "compose.milestone19.yml"
) | ForEach-Object { Join-Path $repositoryRoot "infra/compose/acceptance/$_" }
$arguments = @("compose", "--env-file", $environmentFile)
foreach ($file in $composeFiles) { $arguments += @("--file", $file) }

$environmentProbe = @"
import os
names = (
    "RUNTIME_AGENT_MEMORY_BYTES",
    "RUNTIME_AGENT_NANO_CPUS",
    "RUNTIME_AGENT_PIDS_LIMIT",
    "RUNTIME_AGENT_MAX_RUNTIMES",
)
print("\n".join(name + "=" + os.environ.get(name, "") for name in names))
"@
$agentEnvironment = & docker @($arguments + @(
    "exec", "-T", "runtime-agent", "python", "-c", $environmentProbe
))
if ($LASTEXITCODE -ne 0) { throw "Could not inspect Runtime Agent hardening settings" }
foreach ($name in @(
    "RUNTIME_AGENT_MEMORY_BYTES=", "RUNTIME_AGENT_NANO_CPUS=",
    "RUNTIME_AGENT_PIDS_LIMIT=", "RUNTIME_AGENT_MAX_RUNTIMES="
)) {
    if (-not ($agentEnvironment | Where-Object { $_.StartsWith($name) })) {
        throw "Missing enforced Runtime Agent setting: $name"
    }
}

$routeText = (& docker @($arguments + @(
    "exec", "-T", "edge", "cat", "/etc/traefik/dynamic/milestone14-base.yml"
))) -join "`n"
foreach ($fragment in @("rateLimit:", "maxRequestBodyBytes:", "contentSecurityPolicyReportOnly:")) {
    if ($routeText -notmatch [Regex]::Escape($fragment)) { throw "Missing edge control: $fragment" }
}

$romMConfig = (& docker @($arguments + @(
    "exec", "-T", "romm", "cat", "/romm/config/config.yml"
))) -join "`n"
if ($LASTEXITCODE -ne 0 -or $romMConfig -notmatch "auto_save_sync:\s*false") {
    throw "RomM cartridge-save synchronization must remain disabled pending restore acceptance"
}

$settings = @{}
Get-Content -LiteralPath $environmentFile | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)=(.*)$') {
        $settings[$Matches[1].Trim()] = $Matches[2].Trim().Trim("'", '"')
    }
}
$publicBase = "https://$($settings.M14_PUBLIC_HOSTNAME)"
$response = Invoke-WebRequest -Uri "$publicBase/api/heartbeat" -TimeoutSec 10
if (-not $response.Headers.'Content-Security-Policy-Report-Only') {
    throw "CSP report-only response header is missing"
}
if (-not $response.Headers.'Permissions-Policy') {
    throw "Permissions Policy response header is missing"
}
$oversizedBody = "x" * 1048577
try {
    Invoke-WebRequest -Uri "$publicBase/__milestone19_request_limit_probe" -Method Post `
        -Body $oversizedBody -ContentType "application/octet-stream" -TimeoutSec 15 | Out-Null
    throw "Oversized public request was accepted"
}
catch {
    if ($_.Exception.Response.StatusCode.value__ -ne 413) { throw }
}

$saveProbeStatus = 0
try {
    $saveProbe = Invoke-WebRequest -Uri "$publicBase/api/saves?rom_id=1" -Method Post `
        -Body $oversizedBody -ContentType "application/octet-stream" -TimeoutSec 15
    $saveProbeStatus = [int]$saveProbe.StatusCode
}
catch {
    if (-not $_.Exception.Response) { throw }
    $saveProbeStatus = [int]$_.Exception.Response.StatusCode
}
if ($saveProbeStatus -eq 413) {
    throw "The dedicated save route rejected a valid-size cartridge save"
}
if ($saveProbeStatus -lt 400) {
    throw "The unauthenticated save-route probe was unexpectedly accepted"
}

Write-Host "Milestone 19 hardening-foundation checks passed."
