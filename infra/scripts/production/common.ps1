Set-StrictMode -Version Latest

$script:RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$script:ComposeFile = Join-Path $script:RepositoryRoot "compose.yml"

function Get-ProductionEnvironmentPath([string]$Path = ".env.production") {
    if ([IO.Path]::IsPathFullyQualified($Path)) {
        return [IO.Path]::GetFullPath($Path)
    }
    return [IO.Path]::GetFullPath((Join-Path $script:RepositoryRoot $Path))
}

function Read-ProductionSettings([string]$Path) {
    $settings = @{}
    Get-Content -LiteralPath $Path | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)=(.*)$') {
            $settings[$Matches[1].Trim()] = $Matches[2].Trim().Trim("'", '"')
        }
    }
    return $settings
}

function Set-ProductionSetting([string]$Path, [string]$Name, [string]$Value) {
    if ($Value.Contains("`r") -or $Value.Contains("`n")) {
        throw "Environment values must be single-line"
    }
    $lines = [Collections.Generic.List[string]](Get-Content -LiteralPath $Path)
    $index = -1
    for ($position = 0; $position -lt $lines.Count; $position++) {
        if ($lines[$position] -match "^$([Regex]::Escape($Name))=") {
            $index = $position
            break
        }
    }
    $line = "$Name=$Value"
    if ($index -ge 0) {
        $lines[$index] = $line
    }
    else {
        $lines.Add($line)
    }
    [IO.File]::WriteAllLines($Path, $lines, [Text.UTF8Encoding]::new($false))
}

function New-ProductionSecret([int]$ByteCount = 32) {
    $bytes = [byte[]]::new($ByteCount)
    [Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return [Convert]::ToHexString($bytes).ToLowerInvariant()
}

function Get-ProductionComposeArguments([string]$EnvironmentPath) {
    return @("compose", "--env-file", $EnvironmentPath, "--file", $script:ComposeFile)
}

function Assert-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command is unavailable: $Name"
    }
}
