[CmdletBinding()]
param(
    [string]$RomPath = "local/test-roms/super-tilt-bro-2.6.nes"
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$composeFile = Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone6.yml"
$stateRoot = Join-Path $repositoryRoot "local/runtime-agent"
$userDataRoot = Join-Path $stateRoot "userdata"
$routeRoot = Join-Path $stateRoot "routes"
$requestRoot = Join-Path $stateRoot "requests"
$environmentFile = Join-Path $repositoryRoot ".env.milestone6"
$resolvedRom = Resolve-Path (Join-Path $repositoryRoot $RomPath)
$romRoot = Split-Path -Parent $resolvedRom.Path

foreach ($directory in @($stateRoot, $userDataRoot, $routeRoot, $requestRoot)) {
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
}

$participantId = "60000000-0000-4000-8000-000000000002"
New-Item -ItemType Directory -Force -Path (Join-Path $userDataRoot $participantId) | Out-Null

docker build --tag retrobrowser/retro-session:milestone6 `
    --file (Join-Path $repositoryRoot "images/retro-session/Dockerfile") $repositoryRoot
if ($LASTEXITCODE -ne 0) { throw "retro-session image build failed" }

$runtimeImageId = docker image inspect --format "{{.Id}}" retrobrowser/retro-session:milestone6
if ($LASTEXITCODE -ne 0 -or -not $runtimeImageId.StartsWith("sha256:")) {
    throw "could not resolve the runtime image digest"
}
$runtimeImage = "retrobrowser/retro-session@$runtimeImageId"

$environment = @(
    "M6_RUNTIME_IMAGE=$runtimeImage"
    "M6_DOCKER_ROM_ROOT=$romRoot"
    "M6_DOCKER_USER_DATA_ROOT=$userDataRoot"
    "M6_DOCKER_ROUTE_ROOT=$routeRoot"
    "M6_DOCKER_REQUEST_ROOT=$requestRoot"
)
Set-Content -LiteralPath $environmentFile -Value $environment -Encoding utf8NoBOM

$sessionId = "60000000-0000-4000-8000-000000000006"
$masterToken = [Convert]::ToHexString(
    [Security.Cryptography.RandomNumberGenerator]::GetBytes(32)
).ToLowerInvariant()
$romHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $resolvedRom.Path).Hash.ToLowerInvariant()
$request = [ordered]@{
    schema_version = 1
    session_id = $sessionId
    participant_id = $participantId
    user_id = "milestone6-user"
    player_name = "MilestoneSix"
    image = $runtimeImage
    rom_path = "/srv/retrobrowser/roms/$($resolvedRom.Path | Split-Path -Leaf)"
    rom_sha256 = $romHash
    core_profile = "nes-milestone2"
    netplay = [ordered]@{ role = "host"; host = $null; port = 55435 }
    stream_subfolder = "/stream/m6-player"
    stream_network = "retrobrowser-m6-stream"
    netplay_network = "retrobrowser-m6-retro-net"
    gpu_profile = "cpu"
    selkies_master_token = $masterToken
}
$request | ConvertTo-Json -Depth 5 | Set-Content `
    -LiteralPath (Join-Path $requestRoot "create.json") -Encoding utf8NoBOM

docker compose --env-file $environmentFile --file $composeFile up `
    --detach --build runtime-agent
if ($LASTEXITCODE -ne 0) { throw "Runtime Agent start failed" }

$deadline = (Get-Date).AddMinutes(2)
do {
    $health = docker inspect --format "{{.State.Health.Status}}" `
        retro-browser-milestone6-runtime-agent-1 2>$null
    if ($health -eq "healthy") { break }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $deadline)
if ($health -ne "healthy") { throw "Runtime Agent did not become healthy" }

docker compose --env-file $environmentFile --file $composeFile run `
    --rm --no-deps runtime-agent-client create /requests/create.json
if ($LASTEXITCODE -ne 0) { throw "Runtime Agent create API call failed" }

$runtimeName = "retrobrowser-runtime-$($participantId.Replace('-', ''))"
$deadline = (Get-Date).AddMinutes(3)
do {
    $runtimeHealth = docker inspect --format "{{.State.Health.Status}}" $runtimeName 2>$null
    if ($runtimeHealth -eq "healthy") { break }
    Start-Sleep -Seconds 3
} while ((Get-Date) -lt $deadline)
if ($runtimeHealth -ne "healthy") { throw "Participant runtime did not become healthy" }

Write-Host "Milestone 6 runtime is healthy; no Runtime Agent TCP port is published."
Write-Host "Run .\infra\scripts\milestone6-stop.ps1 to remove it through the UNIX-socket API."
