[CmdletBinding()]
param(
    [string]$RomMSource = "<separate-romm-worktree>"
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$romMRoot = (Resolve-Path -LiteralPath $RomMSource).Path
$environmentFile = Join-Path $repositoryRoot ".env.milestone14"
if (-not (Test-Path -LiteralPath $environmentFile)) {
    throw "Milestone 19 extends the accepted public stack; run milestone18-start.ps1 first"
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

& (Join-Path $PSScriptRoot "milestone18-verify.ps1") -RequireClean
if ($LASTEXITCODE -ne 0) { throw "Milestone 18 clean-baseline verification failed" }

$settings = Read-EnvSettings $environmentFile
if ((git -C $romMRoot branch --show-current) -ne "feat/external-multiplayer-provider") {
    throw "RomMSource must be on feat/external-multiplayer-provider"
}
docker build --target slim-image --tag retrobrowser/romm:milestone19 `
    --file (Join-Path $romMRoot "docker/Dockerfile") $romMRoot
if ($LASTEXITCODE -ne 0) { throw "Milestone 19 RomM image build failed" }
docker build --tag retrobrowser/retro-session:milestone19 `
    --file (Join-Path $repositoryRoot "images/retro-session/Dockerfile") $repositoryRoot
if ($LASTEXITCODE -ne 0) { throw "Milestone 19 runtime image build failed" }
$runtimeImageId = docker image inspect --format "{{.Id}}" retrobrowser/retro-session:milestone19
$romMImageId = docker image inspect --format "{{.Id}}" retrobrowser/romm:milestone19
if (-not $runtimeImageId.StartsWith("sha256:") -or -not $romMImageId.StartsWith("sha256:")) {
    throw "Could not resolve locally built image digests"
}
Set-EnvSetting "M10_RUNTIME_IMAGE" "retrobrowser/retro-session@$runtimeImageId"
Set-EnvSetting "M12_ROMM_IMAGE" "retrobrowser/romm@$romMImageId"
Set-EnvSetting "M14_ROMM_IMAGE" "retrobrowser/romm@$romMImageId"

$template = Get-Content -Raw -LiteralPath (
    Join-Path $repositoryRoot "infra/traefik/dynamic/milestone19-base.template.yml"
)
$baseRoute = $template.
    Replace("__M14_PUBLIC_HOSTNAME__", $settings.M14_PUBLIC_HOSTNAME.Trim().ToLowerInvariant()).
    Replace("__M14_AUTH_HOSTNAME__", $settings.M14_AUTH_HOSTNAME.Trim().ToLowerInvariant())
$routeFile = Join-Path $settings.M10_DOCKER_ROUTE_ROOT "milestone14-base.yml"
Set-Content -LiteralPath $routeFile -Value $baseRoute -Encoding utf8NoBOM

$composeFiles = @(
    "compose.milestone10.yml", "compose.milestone11.yml", "compose.milestone12.yml",
    "compose.milestone14.yml", "compose.milestone15.yml", "compose.milestone16.yml",
    "compose.milestone17.yml", "compose.milestone18.yml", "compose.milestone19.yml"
) | ForEach-Object { Join-Path $repositoryRoot "infra/compose/acceptance/$_" }
$arguments = @("compose", "--env-file", $environmentFile)
foreach ($file in $composeFiles) { $arguments += @("--file", $file) }
& docker @($arguments + @("up", "--detach", "--build", "--wait"))
if ($LASTEXITCODE -ne 0) { throw "Milestone 19 hardening upgrade failed" }
& docker @($arguments + @("restart", "edge"))
if ($LASTEXITCODE -ne 0) { throw "Milestone 19 edge policy reload failed" }
& docker @($arguments + @("up", "--detach", "--wait", "edge"))
if ($LASTEXITCODE -ne 0) { throw "Milestone 19 edge did not become healthy" }

Write-Host "Milestone 19 hardening foundation is running."
Write-Host "Run milestone19-verify.ps1 and follow docs/milestone-19-production-hardening.md."
