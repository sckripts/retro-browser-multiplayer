[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$envFile = Join-Path $repoRoot ".env.milestone5-public"
$composeFile = Join-Path $repoRoot "infra/compose/acceptance/compose.milestone5.public.yml"

if (-not (Test-Path -LiteralPath $envFile)) {
    throw "Missing $envFile; no Milestone 5 public project can be resolved safely."
}

& docker compose `
    --env-file $envFile `
    -f $composeFile `
    down `
    --remove-orphans

if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose failed with exit code $LASTEXITCODE"
}

Write-Host "Milestone 5 public containers and networks were removed. Certificates, credentials, and ROM remain local."
