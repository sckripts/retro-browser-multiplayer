[CmdletBinding()]
param(
    [string]$EnvironmentFile = ".env.production",
    [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")
Assert-Command docker

$environmentPath = Get-ProductionEnvironmentPath $EnvironmentFile
if (-not (Test-Path -LiteralPath $environmentPath)) {
    throw "Run initialize.ps1 first"
}
$settings = Read-ProductionSettings $environmentPath
$required = @(
    "RUNTIME_AGENT_IMAGE", "SESSION_MANAGER_IMAGE", "RETRO_SESSION_IMAGE", "ROMM_IMAGE",
    "PUBLIC_HOSTNAME", "AUTH_HOSTNAME", "TURN_HOST", "TURN_REALM", "TLS_CERT_FILE",
    "TLS_KEY_FILE", "ROM_ROOT", "USER_DATA_ROOT", "SAVE_DATA_ROOT", "ROUTE_CONFIG_ROOT",
    "METRICS_TARGET_ROOT", "SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD",
    "SMTP_FROM", "ADMIN_EMAIL", "SERVICE_TOKEN", "ORCHESTRATION_SECRET",
    "AUTHENTIK_SECRET_KEY", "AUTHENTIK_POSTGRES_PASSWORD", "AUTHENTIK_BOOTSTRAP_PASSWORD",
    "AUTHENTIK_BOOTSTRAP_TOKEN", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET", "ROMM_DB_PASSWORD",
    "ROMM_DB_ROOT_PASSWORD", "ROMM_AUTH_SECRET_KEY", "TURN_SHARED_SECRET",
    "TURN_REST_API_KEY", "GRAFANA_ADMIN_PASSWORD"
)
foreach ($name in $required) {
    if (-not $settings.ContainsKey($name) -or [string]::IsNullOrWhiteSpace($settings[$name])) {
        throw "Missing production setting: $name"
    }
}
foreach ($name in @("RUNTIME_AGENT_IMAGE", "SESSION_MANAGER_IMAGE", "RETRO_SESSION_IMAGE", "ROMM_IMAGE")) {
    if ($settings[$name] -notmatch '^[^\s@]+@sha256:[0-9a-f]{64}$') {
        throw "$name must be an immutable name@sha256 reference"
    }
}
foreach ($name in @("PUBLIC_HOSTNAME", "AUTH_HOSTNAME", "TURN_HOST")) {
    $value = $settings[$name].ToLowerInvariant()
    if ($value -notmatch '^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])$' -or
        $value.EndsWith(".test") -or $value.EndsWith(".example") -or
        $value -match '^\d+(?:\.\d+){3}$') {
        throw "$name must be a public DNS hostname"
    }
}
foreach ($name in @("ROM_ROOT", "USER_DATA_ROOT", "SAVE_DATA_ROOT", "ROUTE_CONFIG_ROOT", "METRICS_TARGET_ROOT")) {
    if (-not [IO.Path]::IsPathFullyQualified($settings[$name])) {
        throw "$name must be an absolute host path"
    }
    New-Item -ItemType Directory -Force -Path $settings[$name] | Out-Null
}
foreach ($name in @("TLS_CERT_FILE", "TLS_KEY_FILE")) {
    if (-not [IO.Path]::IsPathFullyQualified($settings[$name]) -or
        -not (Test-Path -LiteralPath $settings[$name] -PathType Leaf)) {
        throw "$name must point to an existing absolute file"
    }
}
if ($settings.SMTP_USE_TLS -eq "true" -and $settings.SMTP_USE_SSL -eq "true") {
    throw "Enable SMTP STARTTLS or implicit SSL, not both"
}

$certificate = [Security.Cryptography.X509Certificates.X509Certificate2]::CreateFromPemFile(
    $settings.TLS_CERT_FILE, $settings.TLS_KEY_FILE
)
try {
    $now = [DateTimeOffset]::Now
    if ($now -lt $certificate.NotBefore -or $now -gt $certificate.NotAfter) {
        throw "The configured TLS certificate is not currently valid"
    }
    foreach ($hostname in @($settings.PUBLIC_HOSTNAME, $settings.AUTH_HOSTNAME, $settings.TURN_HOST) | Select-Object -Unique) {
        if (-not $certificate.MatchesHostname($hostname)) {
            throw "The configured TLS certificate does not match $hostname"
        }
    }
}
finally {
    $certificate.Dispose()
}

$templatePath = Join-Path $script:RepositoryRoot "infra/traefik/dynamic/production.template.yml"
$routeText = [IO.File]::ReadAllText($templatePath).
    Replace("__PUBLIC_HOSTNAME__", $settings.PUBLIC_HOSTNAME.ToLowerInvariant()).
    Replace("__AUTH_HOSTNAME__", $settings.AUTH_HOSTNAME.ToLowerInvariant())
$routePath = Join-Path $settings.ROUTE_CONFIG_ROOT "base.yml"
[IO.File]::WriteAllText($routePath, $routeText, [Text.UTF8Encoding]::new($false))
$emptyTarget = Join-Path $settings.METRICS_TARGET_ROOT "empty.json"
if (-not (Test-Path -LiteralPath $emptyTarget)) {
    [IO.File]::WriteAllText($emptyTarget, "[]`n", [Text.UTF8Encoding]::new($false))
}

$arguments = Get-ProductionComposeArguments $environmentPath
& docker @($arguments + @("config", "--quiet"))
if ($LASTEXITCODE -ne 0) {
    throw "Production Compose validation failed"
}
& docker @($arguments + @("up", "--detach", "--wait"))
if ($LASTEXITCODE -ne 0) {
    throw "Production deployment failed"
}

Write-Host "Retro Browser is running at https://$($settings.PUBLIC_HOSTNAME)"
if ($OpenBrowser) {
    Start-Process "https://$($settings.PUBLIC_HOSTNAME)/login"
}
