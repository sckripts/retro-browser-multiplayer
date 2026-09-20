[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "milestone16-stop.ps1")
if ($LASTEXITCODE -ne 0) { throw "Milestone 17 stack stop failed" }
