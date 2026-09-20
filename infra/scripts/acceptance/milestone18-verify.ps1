[CmdletBinding()]
param(
    [switch]$RequireRomMUsers,
    [switch]$RequireClean
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$environmentFile = Join-Path $repositoryRoot ".env.milestone14"
if (-not (Test-Path -LiteralPath $environmentFile)) { throw "Run milestone18-start.ps1 first" }
$composeFiles = @(
    "compose.milestone10.yml", "compose.milestone11.yml", "compose.milestone12.yml",
    "compose.milestone14.yml", "compose.milestone15.yml", "compose.milestone16.yml",
    "compose.milestone17.yml", "compose.milestone18.yml"
) | ForEach-Object { Join-Path $repositoryRoot "infra/compose/acceptance/$_" }
$arguments = @("compose", "--env-file", $environmentFile)
foreach ($file in $composeFiles) { $arguments += @("--file", $file) }

& (Join-Path $PSScriptRoot "milestone17-verify.ps1") -RequireRomMUsers:$RequireRomMUsers -RequireClean:$RequireClean
if ($LASTEXITCODE -ne 0) { throw "Milestone 17 verification failed" }

$capacity = & docker @($arguments + @("exec", "-T", "runtime-agent", "python", "-m", "retro_runtime.client", "capacity")) | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $capacity.maximum -lt 1 -or $capacity.used -gt $capacity.maximum) {
    throw "Runtime capacity reporting failed"
}
& docker @($arguments + @("exec", "-T", "prometheus", "promtool", "check", "config", "/etc/prometheus/prometheus.yml"))
if ($LASTEXITCODE -ne 0) { throw "Prometheus configuration validation failed" }
$sessionMetrics = (& docker @($arguments + @("exec", "-T", "prometheus", "wget", "-qO-", "http://session-manager:8080/metrics"))) -join "`n"
if ($LASTEXITCODE -ne 0 -or $sessionMetrics -notmatch "retrobrowser_runtime_capacity") {
    throw "Session Manager metrics scrape failed"
}
& docker @($arguments + @("exec", "-T", "prometheus", "wget", "-qO-", "http://coturn:9641/metrics")) | Out-Null
if ($LASTEXITCODE -ne 0) { throw "coturn metrics scrape failed" }
$grafanaHealth = Invoke-RestMethod -Uri "http://127.0.0.1:3000/api/health" -TimeoutSec 5
if ($grafanaHealth.database -ne "ok") { throw "Grafana health check failed" }
$settings = @{}
Get-Content -LiteralPath $environmentFile | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)=(.*)$') { $settings[$Matches[1].Trim()] = $Matches[2].Trim() }
}
$credential = [Convert]::ToBase64String(
    [Text.Encoding]::UTF8.GetBytes("admin:$($settings.M18_GRAFANA_ADMIN_PASSWORD)")
)
$dashboard = Invoke-RestMethod -Headers @{ Authorization = "Basic $credential" } `
    -Uri "http://127.0.0.1:3000/api/dashboards/uid/retrobrowser-operations" -TimeoutSec 5
if ($dashboard.dashboard.uid -ne "retrobrowser-operations") {
    throw "Grafana dashboard provisioning failed"
}
if ($RequireClean) {
    $targets = Get-ChildItem -LiteralPath $settings.M18_DOCKER_METRICS_TARGET_ROOT -Filter "runtime-*.json"
    if ($targets.Count -ne 0) { throw "Generated Selkies metrics targets remain" }
}

Write-Host "Milestone 18 automated observability checks passed."
