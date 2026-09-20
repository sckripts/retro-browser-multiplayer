[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$composeFile = Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone9.yml"
$environmentFile = Join-Path $repositoryRoot ".env.milestone9"

$created = docker compose --env-file $environmentFile --file $composeFile exec -T `
    session-manager python -m retro_sessions.client create `
    --name "Milestone 9 Secure Stream" --user-id milestone9-host --display-name "Milestone Host"
if ($LASTEXITCODE -ne 0) { throw "create API call failed" }
$session = $created | ConvertFrom-Json

$verified = docker compose --env-file $environmentFile --file $composeFile exec -T `
    session-manager python -m retro_sessions.client verify-stream $session.session_id `
    --user-id milestone9-host --display-name "Milestone Host"
if ($LASTEXITCODE -ne 0 -or $verified -ne "secure stream gate verified") {
    throw "secure stream verification failed"
}

$forbidden = docker compose --env-file $environmentFile --file $composeFile exec -T `
    session-manager python -m retro_sessions.client launch $session.session_id `
    --user-id milestone9-intruder --display-name "Milestone Intruder" 2>$null
if ($LASTEXITCODE -eq 0) { throw "non-participant unexpectedly received launch access" }

$left = docker compose --env-file $environmentFile --file $composeFile exec -T `
    session-manager python -m retro_sessions.client leave $session.session_id `
    --user-id milestone9-host --display-name "Milestone Host"
if ($LASTEXITCODE -ne 0) { throw "leave API call failed" }
$leftSession = $left | ConvertFrom-Json
if ($leftSession.participants[0].state -ne "LEFT") { throw "participant was not retired" }

Write-Host "Milestone 9 verification passed: unauthorized launch denied, tokenless gameplay rejected, scoped token accepted, and leave retired access."
