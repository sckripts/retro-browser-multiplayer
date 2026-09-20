[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$environmentFile = Join-Path $repositoryRoot ".env.milestone14"
$composeFiles = @(
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone10.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone11.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone12.yml")
    (Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone14.yml")
)
if (-not (Test-Path -LiteralPath $environmentFile)) { exit 0 }
$arguments = @("compose", "--env-file", $environmentFile)
foreach ($file in $composeFiles) { $arguments += @("--file", $file) }

$listed = & docker @($arguments + @("exec", "-T", "runtime-agent", "python", "-m", "retro_runtime.client", "list"))
if ($LASTEXITCODE -eq 0) {
    $records = ($listed | ConvertFrom-Json).items
    foreach ($record in $records) {
        & docker @($arguments + @("exec", "-T", "runtime-agent", "python", "-m", "retro_runtime.client", "remove", $record.participant_id))
        if ($LASTEXITCODE -ne 0) { throw "Could not remove runtime $($record.participant_id)" }
    }
}
& docker @($arguments + @("down", "--remove-orphans"))
if ($LASTEXITCODE -ne 0) { throw "Milestone 14 stack stop failed" }
Write-Host "Milestone 14 containers, dynamic runtimes, and networks were removed; data and credentials remain local."
