[CmdletBinding()]
param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$environmentFile = Join-Path $repositoryRoot ".env.milestone14"
if (-not (Test-Path -LiteralPath $environmentFile)) {
    throw "Milestone 18 extends the accepted public stack; run milestone17-start.ps1 first"
}

function Read-EnvSettings([string]$Path) {
    $result = @{}
    Get-Content -LiteralPath $Path | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)=(.*)$') {
            $result[$Matches[1].Trim()] = $Matches[2].Trim().Trim("'", '"')
        }
    }
    return $result
}

function Set-EnvSetting([string]$Name, [string]$Value) {
    $lines = [Collections.Generic.List[string]](Get-Content -LiteralPath $environmentFile)
    $index = -1
    for ($position = 0; $position -lt $lines.Count; $position++) {
        if ($lines[$position] -match "^$([Regex]::Escape($Name))=") { $index = $position; break }
    }
    $line = "$Name=$Value"
    if ($index -ge 0) { $lines[$index] = $line } else { $lines.Add($line) }
    $lines | Set-Content -LiteralPath $environmentFile -Encoding utf8NoBOM
}

$settings = Read-EnvSettings $environmentFile
$composeFiles = @(
    "compose.milestone10.yml", "compose.milestone11.yml", "compose.milestone12.yml",
    "compose.milestone14.yml", "compose.milestone15.yml", "compose.milestone16.yml",
    "compose.milestone17.yml", "compose.milestone18.yml"
) | ForEach-Object { Join-Path $repositoryRoot "infra/compose/acceptance/$_" }
$arguments = @("compose", "--env-file", $environmentFile)
foreach ($file in $composeFiles) { $arguments += @("--file", $file) }

$preflightArguments = $arguments[0..($arguments.Count - 3)]
$listed = & docker @($preflightArguments + @("exec", "-T", "runtime-agent", "python", "-m", "retro_runtime.client", "list"))
if ($LASTEXITCODE -ne 0) { throw "The accepted Milestone 17 Runtime Agent is unavailable" }
if ((($listed | ConvertFrom-Json).items).Count -ne 0) {
    throw "Close active lobbies before enabling observability"
}

$targetRoot = Join-Path $repositoryRoot "local/runtime-agent-m18/targets"
New-Item -ItemType Directory -Force -Path $targetRoot | Out-Null
[IO.File]::WriteAllText((Join-Path $targetRoot "empty.json"), "[]`n")
Set-EnvSetting "M18_DOCKER_METRICS_TARGET_ROOT" ([IO.Path]::GetFullPath($targetRoot))
if ([string]::IsNullOrWhiteSpace($settings.M18_GRAFANA_ADMIN_PASSWORD)) {
    $bytes = [byte[]]::new(32)
    [Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    Set-EnvSetting "M18_GRAFANA_ADMIN_PASSWORD" ([Convert]::ToHexString($bytes).ToLowerInvariant())
}
if ([string]::IsNullOrWhiteSpace($settings.M18_RUNTIME_CAPACITY)) {
    Set-EnvSetting "M18_RUNTIME_CAPACITY" "8"
}

docker build --tag retrobrowser/retro-session:milestone18 `
    --file (Join-Path $repositoryRoot "images/retro-session/Dockerfile") $repositoryRoot
if ($LASTEXITCODE -ne 0) { throw "Milestone 18 runtime image build failed" }
$runtimeImageId = docker image inspect --format "{{.Id}}" retrobrowser/retro-session:milestone18
if (-not $runtimeImageId.StartsWith("sha256:")) { throw "Could not resolve runtime image digest" }
Set-EnvSetting "M10_RUNTIME_IMAGE" "retrobrowser/retro-session@$runtimeImageId"

& docker @($arguments + @("up", "--detach", "--build", "--wait"))
if ($LASTEXITCODE -ne 0) { throw "Milestone 18 observability upgrade failed" }

Write-Host "Milestone 18 observability is running."
Write-Host "Grafana: http://127.0.0.1:3000 (admin; password is in the ignored environment file)."
Write-Host "Follow docs/milestone-18-observability.md and the operational runbooks."
if (-not $NoBrowser) { Start-Process "http://127.0.0.1:3000" }
