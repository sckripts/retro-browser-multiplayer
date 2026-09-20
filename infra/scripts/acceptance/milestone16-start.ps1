[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$GenesisRomPath,
    [string]$RomMSource = "<separate-romm-worktree>",
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$environmentFile = Join-Path $repositoryRoot ".env.milestone14"
if (-not (Test-Path -LiteralPath $environmentFile)) {
    throw "Milestone 16 extends the accepted public stack; run milestone15-start.ps1 first"
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
foreach ($name in @("M10_DOCKER_ROM_ROOT", "M14_PUBLIC_HOSTNAME")) {
    if ([string]::IsNullOrWhiteSpace($settings[$name])) { throw "$name is missing from $environmentFile" }
}
$romMRoot = (Resolve-Path -LiteralPath $RomMSource).Path
if ((git -C $romMRoot branch --show-current) -ne "feat/external-multiplayer-provider") {
    throw "RomMSource must be on feat/external-multiplayer-provider"
}
$candidate = if ([IO.Path]::IsPathRooted($GenesisRomPath)) {
    $GenesisRomPath
} else {
    Join-Path $repositoryRoot $GenesisRomPath
}
$resolvedRom = (Resolve-Path -LiteralPath $candidate).Path
if ([IO.Path]::GetExtension($resolvedRom).ToLowerInvariant() -notin @(".md", ".bin", ".gen")) {
    throw "Milestone 16 accepts only an operator-selected .md, .bin, or .gen Genesis ROM"
}

$composeFiles = @(
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone10.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone11.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone12.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone14.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone15.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone16.yml")
)
$composeArgs = @("compose", "--env-file", $environmentFile)
foreach ($file in $composeFiles) { $composeArgs += @("--file", $file) }

$listed = & docker @($composeArgs + @("exec", "-T", "runtime-agent", "python", "-m", "retro_runtime.client", "list"))
if ($LASTEXITCODE -ne 0) { throw "The accepted Milestone 15 Runtime Agent is unavailable" }
if ((($listed | ConvertFrom-Json).items).Count -ne 0) {
    throw "Close active lobbies before upgrading the runtime image"
}

$libraryRoot = [IO.Path]::GetFullPath($settings.M10_DOCKER_ROM_ROOT)
$genesisDirectory = Join-Path $libraryRoot "genesis/roms"
New-Item -ItemType Directory -Force -Path $genesisDirectory | Out-Null
$managedRom = Join-Path $genesisDirectory (Split-Path -Leaf $resolvedRom)
$resolvedManagedRom = if (Test-Path -LiteralPath $managedRom -PathType Leaf) {
    (Resolve-Path -LiteralPath $managedRom).Path
} else {
    [IO.Path]::GetFullPath($managedRom)
}
if (-not [StringComparer]::OrdinalIgnoreCase.Equals($resolvedRom, $resolvedManagedRom)) {
    Copy-Item -LiteralPath $resolvedRom -Destination $managedRom -Force
}

docker build --tag retrobrowser/retro-session:milestone16 `
    --file (Join-Path $repositoryRoot "images/retro-session/Dockerfile") $repositoryRoot
if ($LASTEXITCODE -ne 0) { throw "Milestone 16 runtime image build failed" }
$runtimeImageId = docker image inspect --format "{{.Id}}" retrobrowser/retro-session:milestone16
if (-not $runtimeImageId.StartsWith("sha256:")) { throw "Could not resolve runtime image digest" }
Set-EnvSetting "M10_RUNTIME_IMAGE" "retrobrowser/retro-session@$runtimeImageId"
Set-EnvSetting "M16_GENESIS_ROM_FILENAME" (Split-Path -Leaf $managedRom)
Set-EnvSetting "M16_GENESIS_ROM_SHA256" ((Get-FileHash -Algorithm SHA256 -LiteralPath $managedRom).Hash.ToLowerInvariant())

& docker @($composeArgs + @("up", "--detach", "--build", "--wait"))
if ($LASTEXITCODE -ne 0) { throw "Milestone 16 public stack upgrade failed" }

Write-Host "Milestone 16 code is running at https://$($settings.M14_PUBLIC_HOSTNAME)"
Write-Host "Scan the Genesis platform in RomM, then follow docs/milestone-16-genesis.md."
if (-not $NoBrowser) { Start-Process "https://$($settings.M14_PUBLIC_HOSTNAME)" }
