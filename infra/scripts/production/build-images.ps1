[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$RomMSource,
    [Parameter(Mandatory)]
    [ValidatePattern('^[0-9a-f]{40}$')]
    [string]$RomMCommit,
    [string]$EnvironmentFile = ".env.production"
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")
Assert-Command docker

$environmentPath = Get-ProductionEnvironmentPath $EnvironmentFile
if (-not (Test-Path -LiteralPath $environmentPath)) {
    throw "Run initialize.ps1 before building images"
}
$romMRoot = (Resolve-Path -LiteralPath $RomMSource).Path
$actualCommit = git -C $romMRoot rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $actualCommit -ne $RomMCommit) {
    throw "RomMSource is not at the explicitly approved commit"
}
if (git -C $romMRoot status --porcelain) {
    throw "RomMSource must have a clean worktree for a production build"
}

$images = @(
    @{
        Name = "RUNTIME_AGENT_IMAGE"
        Tag = "retrobrowser/runtime-agent:local"
        Dockerfile = Join-Path $script:RepositoryRoot "services/runtime-agent/Dockerfile"
        Context = $script:RepositoryRoot
        Target = $null
    },
    @{
        Name = "SESSION_MANAGER_IMAGE"
        Tag = "retrobrowser/session-manager:local"
        Dockerfile = Join-Path $script:RepositoryRoot "services/session-manager/Dockerfile"
        Context = $script:RepositoryRoot
        Target = $null
    },
    @{
        Name = "RETRO_SESSION_IMAGE"
        Tag = "retrobrowser/retro-session:local"
        Dockerfile = Join-Path $script:RepositoryRoot "images/retro-session/Dockerfile"
        Context = $script:RepositoryRoot
        Target = $null
    },
    @{
        Name = "ROMM_IMAGE"
        Tag = "retrobrowser/romm-integration:local"
        Dockerfile = Join-Path $romMRoot "docker/Dockerfile"
        Context = $romMRoot
        Target = "slim-image"
    }
)

foreach ($image in $images) {
    $arguments = @("build", "--file", $image.Dockerfile, "--tag", $image.Tag)
    if ($image.Target) {
        $arguments += @("--target", $image.Target)
    }
    $arguments += $image.Context
    & docker @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Image build failed: $($image.Name)"
    }
    $imageId = docker image inspect --format "{{.Id}}" $image.Tag
    if ($LASTEXITCODE -ne 0 -or $imageId -notmatch '^sha256:[0-9a-f]{64}$') {
        throw "Could not resolve an immutable image ID for $($image.Name)"
    }
    Set-ProductionSetting $environmentPath $image.Name "$($image.Tag.Split(':')[0])@$imageId"
}

Write-Host "Production image references were written to $environmentPath"
