[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$composeFile = Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone8.yml"
$environmentFile = Join-Path $repositoryRoot ".env.milestone8"

if (Test-Path -LiteralPath $environmentFile) {
    $listed = docker compose --env-file $environmentFile --file $composeFile exec -T `
        runtime-agent python -m retro_runtime.client list
    if ($LASTEXITCODE -eq 0) {
        $records = ($listed | ConvertFrom-Json).items
        foreach ($record in $records) {
            docker compose --env-file $environmentFile --file $composeFile exec -T `
                runtime-agent python -m retro_runtime.client remove $record.participant_id
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "Could not remove runtime $($record.participant_id) through the agent."
            }
        }
    }
    docker compose --env-file $environmentFile --file $composeFile down --remove-orphans
    if ($LASTEXITCODE -ne 0) { throw "Milestone 8 stack shutdown failed" }
}
