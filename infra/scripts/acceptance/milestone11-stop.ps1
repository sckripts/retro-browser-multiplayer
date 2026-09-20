[CmdletBinding()]
param(
    [switch]$RemoveData
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$composeFile = Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone11.yml"
$environmentFile = Join-Path $repositoryRoot ".env.milestone11"

if (Test-Path -LiteralPath $environmentFile) {
    $arguments = @("compose", "--env-file", $environmentFile, "--file", $composeFile, "down", "--remove-orphans")
    if ($RemoveData) { $arguments += "--volumes" }
    & docker @arguments
    if ($LASTEXITCODE -ne 0) { throw "Milestone 11 stack shutdown failed" }
}

if ($RemoveData) {
    Write-Host "Removed the Milestone 11 containers, networks, and named data volumes."
} else {
    Write-Host "Stopped Milestone 11 and preserved its identity/database volumes."
}
