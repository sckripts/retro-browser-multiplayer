[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$composeFile = Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone6.yml"
$environmentFile = Join-Path $repositoryRoot ".env.milestone6"
$participantId = "60000000-0000-4000-8000-000000000002"

if (Test-Path -LiteralPath $environmentFile) {
    docker compose --env-file $environmentFile --file $composeFile run `
        --rm --no-deps runtime-agent-client remove $participantId
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "The API removal did not succeed; inspect the agent before manual cleanup."
    }
    docker compose --env-file $environmentFile --file $composeFile down --remove-orphans
    if ($LASTEXITCODE -ne 0) { throw "Milestone 6 stack shutdown failed" }
}
