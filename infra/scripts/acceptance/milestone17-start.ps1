[CmdletBinding()]
param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$environmentFile = Join-Path $repositoryRoot ".env.milestone14"
if (-not (Test-Path -LiteralPath $environmentFile)) {
    throw "Milestone 17 extends the accepted public stack; run milestone16-start.ps1 first"
}

function Read-EnvSettings([string]$Path) {
    $result = @{}
    Get-Content -LiteralPath $Path | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)=(.*)$') {
            $value = $Matches[2].Trim()
            if ($value.Length -ge 2 -and
                (($value.StartsWith("'") -and $value.EndsWith("'")) -or
                ($value.StartsWith('"') -and $value.EndsWith('"')))) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            $result[$Matches[1].Trim()] = $value
        }
    }
    return $result
}

function Set-EnvSetting([string]$Name, [string]$Value) {
    $lines = [Collections.Generic.List[string]](Get-Content -LiteralPath $environmentFile)
    $index = -1
    for ($position = 0; $position -lt $lines.Count; $position++) {
        if ($lines[$position] -match "^$([Regex]::Escape($Name))=") {
            $index = $position
            break
        }
    }
    $line = "$Name=$Value"
    if ($index -ge 0) { $lines[$index] = $line } else { $lines.Add($line) }
    $lines | Set-Content -LiteralPath $environmentFile -Encoding utf8NoBOM
}

$settings = Read-EnvSettings $environmentFile
if ([string]::IsNullOrWhiteSpace($settings.M14_PUBLIC_HOSTNAME)) {
    throw "M14_PUBLIC_HOSTNAME is missing from $environmentFile"
}

$composeFiles = @(
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone10.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone11.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone12.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone14.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone15.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone16.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone17.yml")
)
$composeArgs = @("compose", "--env-file", $environmentFile)
foreach ($file in $composeFiles) { $composeArgs += @("--file", $file) }

$preflightArgs = @("compose", "--env-file", $environmentFile)
foreach ($file in $composeFiles[0..5]) { $preflightArgs += @("--file", $file) }
$listed = & docker @($preflightArgs + @("exec", "-T", "runtime-agent", "python", "-m", "retro_runtime.client", "list"))
if ($LASTEXITCODE -ne 0) { throw "The accepted Milestone 16 Runtime Agent is unavailable" }
if ((($listed | ConvertFrom-Json).items).Count -ne 0) {
    throw "Close active lobbies before enabling persistence"
}

$saveRoot = Join-Path $repositoryRoot "local/runtime-agent-m17/saves"
New-Item -ItemType Directory -Force -Path $saveRoot | Out-Null
$saveRoot = [IO.Path]::GetFullPath($saveRoot)
Set-EnvSetting "M17_DOCKER_SAVE_ROOT" $saveRoot

docker build --tag retrobrowser/retro-session:milestone17 `
    --file (Join-Path $repositoryRoot "images/retro-session/Dockerfile") $repositoryRoot
if ($LASTEXITCODE -ne 0) { throw "Milestone 17 runtime image build failed" }
$runtimeImageId = docker image inspect --format "{{.Id}}" retrobrowser/retro-session:milestone17
if (-not $runtimeImageId.StartsWith("sha256:")) { throw "Could not resolve runtime image digest" }
Set-EnvSetting "M10_RUNTIME_IMAGE" "retrobrowser/retro-session@$runtimeImageId"

& docker @($composeArgs + @("up", "--detach", "--build", "--wait"))
if ($LASTEXITCODE -ne 0) { throw "Milestone 17 public stack upgrade failed" }

Write-Host "Milestone 17 persistence is running at https://$($settings.M14_PUBLIC_HOSTNAME)"
Write-Host "Follow docs/milestone-17-persistence.md for acceptance."
if (-not $NoBrowser) { Start-Process "https://$($settings.M14_PUBLIC_HOSTNAME)" }
