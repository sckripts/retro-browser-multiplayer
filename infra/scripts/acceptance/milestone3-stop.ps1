[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$envFile = Join-Path $repoRoot ".env.milestone3"
$composeFile = Join-Path $repoRoot "infra/compose/acceptance/compose.public-test.yml"

if (-not (Test-Path -LiteralPath $envFile)) {
    throw "Missing $envFile; no Milestone 3 project can be resolved safely."
}

& docker compose `
    --env-file $envFile `
    -f $composeFile `
    down `
    --remove-orphans

if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose failed with exit code $LASTEXITCODE"
}

Write-Host "Milestone 3 containers and networks were removed. Certificates, credentials, and ROM remain local."
