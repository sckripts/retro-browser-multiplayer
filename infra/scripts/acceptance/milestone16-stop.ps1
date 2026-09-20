[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "milestone15-stop.ps1")
if ($LASTEXITCODE -ne 0) { throw "Milestone 16 stack stop failed" }
