[CmdletBinding()]
param(
    [string]$EnvironmentFile = ".env.production"
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")

$environmentPath = Get-ProductionEnvironmentPath $EnvironmentFile
$templatePath = Join-Path $script:RepositoryRoot ".env.production.example"
if (-not (Test-Path -LiteralPath $environmentPath)) {
    Copy-Item -LiteralPath $templatePath -Destination $environmentPath
}

$settings = Read-ProductionSettings $environmentPath
$secretSizes = @{
    SERVICE_TOKEN = 32
    ORCHESTRATION_SECRET = 32
    AUTHENTIK_SECRET_KEY = 64
    AUTHENTIK_POSTGRES_PASSWORD = 32
    AUTHENTIK_BOOTSTRAP_PASSWORD = 32
    AUTHENTIK_BOOTSTRAP_TOKEN = 32
    OIDC_CLIENT_SECRET = 32
    ROMM_DB_PASSWORD = 32
    ROMM_DB_ROOT_PASSWORD = 32
    ROMM_AUTH_SECRET_KEY = 64
    TURN_SHARED_SECRET = 32
    TURN_REST_API_KEY = 32
    GRAFANA_ADMIN_PASSWORD = 32
}
foreach ($entry in $secretSizes.GetEnumerator()) {
    if (-not $settings.ContainsKey($entry.Key) -or
        [string]::IsNullOrWhiteSpace($settings[$entry.Key])) {
        Set-ProductionSetting $environmentPath $entry.Key (New-ProductionSecret $entry.Value)
    }
}

$pathDefaults = @{
    ROM_ROOT = "local/production/library"
    USER_DATA_ROOT = "local/production/runtime-userdata"
    SAVE_DATA_ROOT = "local/production/saves"
    ROUTE_CONFIG_ROOT = "local/production/routes"
    METRICS_TARGET_ROOT = "local/production/metrics-targets"
}
$settings = Read-ProductionSettings $environmentPath
foreach ($entry in $pathDefaults.GetEnumerator()) {
    $value = $settings[$entry.Key]
    if ([string]::IsNullOrWhiteSpace($value)) {
        $value = [IO.Path]::GetFullPath((Join-Path $script:RepositoryRoot $entry.Value))
        Set-ProductionSetting $environmentPath $entry.Key $value
    }
    elseif (-not [IO.Path]::IsPathFullyQualified($value)) {
        throw "$($entry.Key) must be an absolute host path"
    }
    New-Item -ItemType Directory -Force -Path $value | Out-Null
}

$settings = Read-ProductionSettings $environmentPath
$emptyTarget = Join-Path $settings.METRICS_TARGET_ROOT "empty.json"
if (-not (Test-Path -LiteralPath $emptyTarget)) {
    [IO.File]::WriteAllText($emptyTarget, "[]`n", [Text.UTF8Encoding]::new($false))
}
if (-not $IsWindows) {
    chmod 600 $environmentPath
}

Write-Host "Production configuration initialized at $environmentPath"
Write-Host "Secrets were generated without being printed. Fill the blank image, DNS, TLS, SMTP, and administrator settings before starting."
