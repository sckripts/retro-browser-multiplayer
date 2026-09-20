[CmdletBinding()]
param(
    [switch]$RequireRomMUsers,
    [switch]$RequireGenesisRuntime,
    [switch]$RequireClean
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$environmentFile = Join-Path $repositoryRoot ".env.milestone14"
if (-not (Test-Path -LiteralPath $environmentFile)) { throw "Run milestone16-start.ps1 first" }
$settings = @{}
Get-Content -LiteralPath $environmentFile | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)=(.*)$') { $settings[$Matches[1].Trim()] = $Matches[2].Trim() }
}
$composeFiles = @(
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone10.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone11.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone12.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone14.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone15.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone16.yml")
)
$arguments = @("compose", "--env-file", $environmentFile)
foreach ($file in $composeFiles) { $arguments += @("--file", $file) }

$baseArguments = @{
    RequireRomMUsers = $RequireRomMUsers
    RequireClean = $RequireClean
}
& (Join-Path $PSScriptRoot "milestone15-verify.ps1") @baseArguments
if ($LASTEXITCODE -ne 0) { throw "Milestone 15 verification failed" }

& docker run --rm --entrypoint sha256sum $settings.M10_RUNTIME_IMAGE `
    --check /opt/retro-session/blastem_libretro.sha256
if ($LASTEXITCODE -ne 0) { throw "The pinned BlastEm artifact failed its embedded hash check" }

if ($RequireGenesisRuntime) {
    $listed = & docker @($arguments + @("exec", "-T", "runtime-agent", "python", "-m", "retro_runtime.client", "list"))
    if ($LASTEXITCODE -ne 0) { throw "Could not list managed runtimes" }
    $records = @(($listed | ConvertFrom-Json).items)
    if ($records.Count -eq 0) { throw "No active runtime exists for Genesis verification" }
    foreach ($record in $records) {
        $containerName = "retrobrowser-runtime-$($record.participant_id.Replace('-', ''))"
        $logLines = & docker logs $containerName 2>&1
        if ($LASTEXITCODE -ne 0) { throw "Could not read logs for $containerName" }
        $logs = $logLines -join "`n"
        if ($logs -notmatch "profile=genesis-blastem") { throw "$containerName is not using genesis-blastem" }
        if ($logs -notmatch "core BlastEm 2026-09-02 SHA-256 52044324adbbda37a36c4d916dfb3bb677bf1952444c48a64d78f1c472991714") {
            throw "$containerName did not verify the pinned BlastEm core"
        }
    }
}

Write-Host "Milestone 16 automated Genesis checks passed."
