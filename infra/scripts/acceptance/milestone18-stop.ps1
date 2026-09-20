[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$environmentFile = Join-Path $repositoryRoot ".env.milestone14"
$composeFiles = @(
    "compose.milestone10.yml", "compose.milestone11.yml", "compose.milestone12.yml",
    "compose.milestone14.yml", "compose.milestone15.yml", "compose.milestone16.yml",
    "compose.milestone17.yml", "compose.milestone18.yml"
) | ForEach-Object { Join-Path $repositoryRoot "infra/compose/acceptance/$_" }
$arguments = @("compose", "--env-file", $environmentFile)
foreach ($file in $composeFiles) { $arguments += @("--file", $file) }
& docker @($arguments + @("down", "--remove-orphans"))
if ($LASTEXITCODE -ne 0) { throw "Milestone 18 stack stop failed" }
