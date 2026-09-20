[CmdletBinding()]
param(
    [string]$RomPath = "local/test-roms/super-tilt-bro-2.6.nes"
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$composeFile = Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone10.yml"
$environmentFile = Join-Path $repositoryRoot ".env.milestone10"
$stateRoot = Join-Path $repositoryRoot "local/runtime-agent-m10"
$userDataRoot = Join-Path $stateRoot "userdata"
$routeRoot = Join-Path $stateRoot "routes"
$resolvedRom = Resolve-Path (Join-Path $repositoryRoot $RomPath)
$romRoot = Split-Path -Parent $resolvedRom.Path

foreach ($directory in @($stateRoot, $userDataRoot, $routeRoot)) {
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
}

docker build --tag retrobrowser/retro-session:milestone10 `
    --file (Join-Path $repositoryRoot "images/retro-session/Dockerfile") $repositoryRoot
if ($LASTEXITCODE -ne 0) { throw "retro-session image build failed" }

$runtimeImageId = docker image inspect --format "{{.Id}}" retrobrowser/retro-session:milestone10
if ($LASTEXITCODE -ne 0 -or -not $runtimeImageId.StartsWith("sha256:")) {
    throw "could not resolve the runtime image digest"
}
$runtimeImage = "retrobrowser/retro-session@$runtimeImageId"
$serviceToken = [Convert]::ToHexString(
    [Security.Cryptography.RandomNumberGenerator]::GetBytes(32)
).ToLowerInvariant()
$orchestrationSecret = [Convert]::ToHexString(
    [Security.Cryptography.RandomNumberGenerator]::GetBytes(32)
).ToLowerInvariant()
$romHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $resolvedRom.Path).Hash.ToLowerInvariant()
$environment = @(
    "M10_RUNTIME_IMAGE=$runtimeImage"
    "M10_DOCKER_ROM_ROOT=$romRoot"
    "M10_DOCKER_USER_DATA_ROOT=$userDataRoot"
    "M10_DOCKER_ROUTE_ROOT=$routeRoot"
    "M10_ROM_FILENAME=$($resolvedRom.Path | Split-Path -Leaf)"
    "M10_ROM_SHA256=$romHash"
    "M10_SERVICE_TOKEN=$serviceToken"
    "M10_ORCHESTRATION_SECRET=$orchestrationSecret"
)
$environment | Set-Content -LiteralPath $environmentFile -Encoding utf8NoBOM

docker compose --env-file $environmentFile --file $composeFile up --detach --build
if ($LASTEXITCODE -ne 0) { throw "Milestone 10 stack start failed" }

$deadline = (Get-Date).AddMinutes(3)
do {
    $health = docker inspect --format "{{.State.Health.Status}}" `
        retro-browser-milestone10-session-manager-1 2>$null
    if ($health -eq "healthy") { break }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $deadline)
if ($health -ne "healthy") { throw "Session Manager did not become ready" }

Write-Host "Milestone 10 is ready. Run .\infra\scripts\milestone10-verify.ps1."
