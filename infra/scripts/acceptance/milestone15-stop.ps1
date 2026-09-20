[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "milestone14-stop.ps1")
if ($LASTEXITCODE -ne 0) { throw "Milestone 15 stack stop failed" }
