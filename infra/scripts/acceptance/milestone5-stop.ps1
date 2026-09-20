[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$envFile = Join-Path $repoRoot ".env.milestone5"
$composeFile = Join-Path $repoRoot "infra/compose/acceptance/compose.milestone5.yml"
$gpuFile = Join-Path $repoRoot "infra/compose/acceptance/compose.milestone5.gpu.yml"

if (-not (Test-Path -LiteralPath $envFile)) {
    Write-Host "No .env.milestone5 file exists; nothing was started by the helper."
    exit 0
}

& docker compose --env-file $envFile -f $composeFile -f $gpuFile down
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose failed with exit code $LASTEXITCODE"
}

Write-Host "Milestone 5 containers and networks were removed. The ignored ROM remains local."
