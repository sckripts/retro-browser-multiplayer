[CmdletBinding()]
param(
    [switch]$RequireRomMUsers,
    [switch]$RequireSnesRuntime,
    [switch]$RequireClean
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$environmentFile = Join-Path $repositoryRoot ".env.milestone14"
if (-not (Test-Path -LiteralPath $environmentFile)) { throw "Run milestone15-start.ps1 first" }
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
)
$arguments = @("compose", "--env-file", $environmentFile)
foreach ($file in $composeFiles) { $arguments += @("--file", $file) }

$baseArguments = @{
    RequireRomMUsers = $RequireRomMUsers
    RequireClean = $RequireClean
}
& (Join-Path $PSScriptRoot "milestone14-verify.ps1") @baseArguments
if ($LASTEXITCODE -ne 0) { throw "Milestone 14 public boundary verification failed" }

if ($RequireRomMUsers) {
    foreach ($name in @("M15_TEST_USER_C_EMAIL", "M15_TEST_USER_D_EMAIL")) {
        if ([string]::IsNullOrWhiteSpace($settings[$name])) { throw "$name is missing" }
    }
    $emails = @(
        $settings.M11_TEST_USER_A_EMAIL, $settings.M11_TEST_USER_B_EMAIL,
        $settings.M15_TEST_USER_C_EMAIL, $settings.M15_TEST_USER_D_EMAIL
    )
    $quotedEmails = ($emails | ForEach-Object { "'$($_.Replace("'", "''"))'" }) -join ","
    $sql = "SELECT id FROM users WHERE email IN ($quotedEmails);"
    $rows = & docker @($arguments + @("exec", "-T", "romm-database", "mariadb", "--batch", "--skip-column-names", "-uromm", "-p$($settings.M11_ROMM_DB_PASSWORD)", "romm", "-e", $sql))
    if ($LASTEXITCODE -ne 0 -or @($rows | Where-Object { $_ -match '\S' }).Count -ne 4) {
        throw "Expected exactly four distinct RomM OIDC users"
    }
}

& docker run --rm --entrypoint sha256sum $settings.M10_RUNTIME_IMAGE `
    --check /opt/retro-session/bsnes_libretro.sha256
if ($LASTEXITCODE -ne 0) { throw "The pinned bsnes artifact failed its embedded hash check" }

if ($RequireSnesRuntime) {
    $listed = & docker @($arguments + @("exec", "-T", "runtime-agent", "python", "-m", "retro_runtime.client", "list"))
    if ($LASTEXITCODE -ne 0) { throw "Could not list managed runtimes" }
    $records = @(($listed | ConvertFrom-Json).items)
    if ($records.Count -eq 0) { throw "No active runtime exists for SNES verification" }
    foreach ($record in $records) {
        $containerName = "retrobrowser-runtime-$($record.participant_id.Replace('-', ''))"
        $logs = docker logs $containerName 2>&1
        if ($logs -notmatch "profile=snes-bsnes") { throw "$containerName is not using snes-bsnes" }
        & docker exec $containerName python3 -c "from pathlib import Path; p=list(Path('/run/retro-session').glob('*/*/config/retroarch.cfg')); assert len(p)==1 and 'input_libretro_device_p2 = \`"257\`"' in p[0].read_text()"
        if ($LASTEXITCODE -ne 0) { throw "$containerName does not have the profile-owned multitap mapping" }
    }
}

Write-Host "Milestone 15 automated SNES checks passed."
