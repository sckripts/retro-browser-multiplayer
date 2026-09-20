[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SnesRomPath,
    [Parameter(Mandatory = $true)]
    [string]$UserCEmail,
    [Parameter(Mandatory = $true)]
    [string]$UserDEmail,
    [string]$RomMSource = "<separate-romm-worktree>",
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$environmentFile = Join-Path $repositoryRoot ".env.milestone14"
if (-not (Test-Path -LiteralPath $environmentFile)) {
    throw "Milestone 15 extends the accepted public stack; run milestone14-start.ps1 first"
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
foreach ($name in @("M10_DOCKER_ROM_ROOT", "M11_BOOTSTRAP_TOKEN", "M14_PUBLIC_HOSTNAME", "M14_AUTH_HOSTNAME")) {
    if ([string]::IsNullOrWhiteSpace($settings[$name])) { throw "$name is missing from $environmentFile" }
}
$testerEmails = @(
    $settings.M11_TEST_USER_A_EMAIL, $settings.M11_TEST_USER_B_EMAIL, $UserCEmail, $UserDEmail
)
$emailPattern = '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}$'
if ($UserCEmail -notmatch $emailPattern -or $UserDEmail -notmatch $emailPattern) {
    throw "UserCEmail and UserDEmail must be ordinary email addresses"
}
if (@($testerEmails | ForEach-Object { $_.ToLowerInvariant() } | Select-Object -Unique).Count -ne 4) {
    throw "Milestone 15 requires four distinct tester email addresses"
}
$romMRoot = (Resolve-Path -LiteralPath $RomMSource).Path
if ((git -C $romMRoot branch --show-current) -ne "feat/external-multiplayer-provider") {
    throw "RomMSource must be on feat/external-multiplayer-provider"
}
$candidate = if ([IO.Path]::IsPathRooted($SnesRomPath)) {
    $SnesRomPath
} else {
    Join-Path $repositoryRoot $SnesRomPath
}
$resolvedRom = (Resolve-Path -LiteralPath $candidate).Path
if ([IO.Path]::GetExtension($resolvedRom).ToLowerInvariant() -notin @(".sfc", ".smc")) {
    throw "Milestone 15 accepts only an operator-selected .sfc or .smc SNES ROM"
}

$composeFiles = @(
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone10.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone11.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone12.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone14.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone15.yml")
)
$composeArgs = @("compose", "--env-file", $environmentFile)
foreach ($file in $composeFiles) { $composeArgs += @("--file", $file) }

$listed = & docker @($composeArgs + @("exec", "-T", "runtime-agent", "python", "-m", "retro_runtime.client", "list"))
if ($LASTEXITCODE -ne 0) { throw "The accepted Milestone 14 Runtime Agent is unavailable" }
if ((($listed | ConvertFrom-Json).items).Count -ne 0) {
    throw "Close active lobbies before upgrading the runtime image"
}

$libraryRoot = [IO.Path]::GetFullPath($settings.M10_DOCKER_ROM_ROOT)
$snesDirectory = Join-Path $libraryRoot "snes/roms"
New-Item -ItemType Directory -Force -Path $snesDirectory | Out-Null
$managedRom = Join-Path $snesDirectory (Split-Path -Leaf $resolvedRom)
$resolvedManagedRom = if (Test-Path -LiteralPath $managedRom -PathType Leaf) {
    (Resolve-Path -LiteralPath $managedRom).Path
} else {
    [IO.Path]::GetFullPath($managedRom)
}
if (-not [StringComparer]::OrdinalIgnoreCase.Equals($resolvedRom, $resolvedManagedRom)) {
    Copy-Item -LiteralPath $resolvedRom -Destination $managedRom -Force
}

docker build --tag retrobrowser/retro-session:milestone15 `
    --file (Join-Path $repositoryRoot "images/retro-session/Dockerfile") $repositoryRoot
if ($LASTEXITCODE -ne 0) { throw "Milestone 15 runtime image build failed" }
$runtimeImageId = docker image inspect --format "{{.Id}}" retrobrowser/retro-session:milestone15
if (-not $runtimeImageId.StartsWith("sha256:")) { throw "Could not resolve runtime image digest" }
Set-EnvSetting "M10_RUNTIME_IMAGE" "retrobrowser/retro-session@$runtimeImageId"
Set-EnvSetting "M15_SNES_ROM_FILENAME" (Split-Path -Leaf $managedRom)
Set-EnvSetting "M15_SNES_ROM_SHA256" ((Get-FileHash -Algorithm SHA256 -LiteralPath $managedRom).Hash.ToLowerInvariant())

& docker @($composeArgs + @("up", "--detach", "--build", "--wait"))
if ($LASTEXITCODE -ne 0) { throw "Milestone 15 public stack upgrade failed" }

$headers = @{ Authorization = "Bearer $($settings.M11_BOOTSTRAP_TOKEN)" }
$authBase = "https://$($settings.M14_AUTH_HOSTNAME)"
foreach ($user in @(
    @{ username = "player-three"; name = "Player Three"; email = $UserCEmail },
    @{ username = "player-four"; name = "Player Four"; email = $UserDEmail }
)) {
    $encodedUsername = [Uri]::EscapeDataString($user.username)
    $existing = Invoke-RestMethod -Uri "$authBase/api/v3/core/users/?username=$encodedUsername" `
        -Headers $headers -TimeoutSec 15
    if ($existing.pagination.count -eq 0) {
        $body = @{
            username = $user.username
            name = $user.name
            email = $user.email
            is_active = $true
            attributes = @{ email_verified = $true }
        } | ConvertTo-Json -Depth 4
        $null = Invoke-RestMethod -Method Post -Uri "$authBase/api/v3/core/users/" `
            -Headers $headers -ContentType "application/json" -Body $body -TimeoutSec 15
    } elseif ($existing.results[0].email -ne $user.email) {
        throw "$($user.username) already exists with a different email address"
    }
}
Set-EnvSetting "M15_TEST_USER_C_EMAIL" $UserCEmail
Set-EnvSetting "M15_TEST_USER_D_EMAIL" $UserDEmail

Write-Host "Milestone 15 code is running at https://$($settings.M14_PUBLIC_HOSTNAME)"
Write-Host "Scan the SNES platform in RomM, then follow docs/milestone-15-snes.md."
if (-not $NoBrowser) { Start-Process "https://$($settings.M14_PUBLIC_HOSTNAME)" }
