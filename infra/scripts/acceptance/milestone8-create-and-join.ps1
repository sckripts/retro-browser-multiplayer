[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$composeFile = Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone8.yml"
$environmentFile = Join-Path $repositoryRoot ".env.milestone8"

$created = docker compose --env-file $environmentFile --file $composeFile exec -T `
    session-manager python -m retro_sessions.client create
if ($LASTEXITCODE -ne 0) { throw "create API call failed" }
$session = $created | ConvertFrom-Json

$joined = docker compose --env-file $environmentFile --file $composeFile exec -T `
    session-manager python -m retro_sessions.client join $session.session_id
if ($LASTEXITCODE -ne 0) { throw "join API call failed" }
$joinedSession = $joined | ConvertFrom-Json

Write-Host "Session $($joinedSession.session_id) has $($joinedSession.player_count) healthy runtimes."
Write-Host "Private Netplay addressing remains absent from the API response."
