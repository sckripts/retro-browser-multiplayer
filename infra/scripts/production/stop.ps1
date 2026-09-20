[CmdletBinding()]
param(
    [string]$EnvironmentFile = ".env.production"
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")
Assert-Command docker

$environmentPath = Get-ProductionEnvironmentPath $EnvironmentFile
if (-not (Test-Path -LiteralPath $environmentPath)) {
    throw "Production environment file not found: $environmentPath"
}
$arguments = Get-ProductionComposeArguments $environmentPath
& docker @($arguments + @("down", "--remove-orphans"))
if ($LASTEXITCODE -ne 0) {
    throw "Production shutdown failed"
}
Write-Host "Production containers and project networks stopped; persistent volumes and host data were retained."
