[CmdletBinding()]
param(
    [switch]$RequireRomMUsers,
    [switch]$RequirePersistentHost,
    [switch]$RequireClean
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$environmentFile = Join-Path $repositoryRoot ".env.milestone14"
if (-not (Test-Path -LiteralPath $environmentFile)) { throw "Run milestone17-start.ps1 first" }
$settings = @{}
Get-Content -LiteralPath $environmentFile | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)=(.*)$') { $settings[$Matches[1].Trim()] = $Matches[2].Trim() }
}
if ([string]::IsNullOrWhiteSpace($settings.M17_DOCKER_SAVE_ROOT)) {
    throw "M17_DOCKER_SAVE_ROOT is not configured"
}
if (-not (Test-Path -LiteralPath $settings.M17_DOCKER_SAVE_ROOT -PathType Container)) {
    throw "The durable save root does not exist"
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
$arguments = @("compose", "--env-file", $environmentFile)
foreach ($file in $composeFiles) { $arguments += @("--file", $file) }

$baseArguments = @{
    RequireRomMUsers = $RequireRomMUsers
    RequireClean = $RequireClean
}
& (Join-Path $PSScriptRoot "milestone16-verify.ps1") @baseArguments
if ($LASTEXITCODE -ne 0) { throw "Milestone 16 verification failed" }

$agentMounts = & docker @($arguments + @("config", "--format", "json")) | ConvertFrom-Json
$saveMount = @($agentMounts.services."runtime-agent".volumes | Where-Object {
    $_.target -eq "/srv/retrobrowser/saves" -and -not $_.read_only
})
if ($saveMount.Count -ne 1) { throw "Runtime Agent does not have exactly one writable save root" }

if ($RequirePersistentHost) {
    $listed = & docker @($arguments + @("exec", "-T", "runtime-agent", "python", "-m", "retro_runtime.client", "list"))
    if ($LASTEXITCODE -ne 0) { throw "Could not list managed runtimes" }
    $records = @(($listed | ConvertFrom-Json).items)
    if ($records.Count -eq 0) { throw "No active runtime exists for persistence verification" }
    $persistentCount = 0
    foreach ($record in $records) {
        $containerName = "retrobrowser-runtime-$($record.participant_id.Replace('-', ''))"
        $inspection = docker inspect $containerName | ConvertFrom-Json
        $saveKey = $inspection[0].Config.Labels."io.retrobrowser.save-key"
        $mounted = @($inspection[0].Mounts | Where-Object {
            $_.Destination -eq "/run/retro-saves" -and $_.RW
        })
        if ($saveKey) {
            $persistentCount++
            if ($saveKey -notmatch '^[a-f0-9]{64}$' -or $mounted.Count -ne 1) {
                throw "$containerName has invalid persistent-save isolation"
            }
        } elseif ($mounted.Count -ne 0) {
            throw "$containerName has a durable mount without host ownership"
        }
    }
    if ($persistentCount -ne 1) { throw "Exactly one Netplay host must own durable saves" }
}

Write-Host "Milestone 17 automated persistence checks passed."
