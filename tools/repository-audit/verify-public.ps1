[CmdletBinding()]
param(
    [switch]$IncludeHistory,
    [string]$HistoryRef
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
Push-Location $repositoryRoot
try {
    $candidateFiles = @(
        git ls-files --cached --others --exclude-standard
    ) | Where-Object { $_ }
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to enumerate repository files."
    }

    $forbiddenExtension = [regex]::new(
        "(?i)\.(32x|7z|bios|bin|chd|cue|fig|gb|gba|gbc|gen|iso|mgd|n64|nes|rar|rom|sav|sfc|smc|srm|state|swc|v64|z64)$"
    )
    $personalFragment = -join [char[]](112, 97, 121, 110, 101)
    $privateAccount = -join [char[]](115, 99, 107, 114, 105, 112, 116, 115)
    $privateDomain = $personalFragment + "rocks.com"
    $userRoot = "C:" + [char]92 + "Users" + [char]92
    $appsRoot = "C:" + [char]92 + "apps" + [char]92
    $mailDomains = @("gmail.com", "hotmail.com", "outlook.com", "yahoo.com")
    $ignoreCase = [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    $forbiddenText = @(
        [regex]::new([regex]::Escape($personalFragment), $ignoreCase),
        [regex]::new([regex]::Escape($privateAccount), $ignoreCase),
        [regex]::new([regex]::Escape($privateDomain), $ignoreCase),
        [regex]::new("\b[A-Z]:\\(?:Users|apps)\\", $ignoreCase),
        [regex]::new("[A-Z0-9._%+-]+@(?:gmail|hotmail|outlook|yahoo)\.[A-Z]{2,}", $ignoreCase)
    )
    $historicalLiterals = @(
        $personalFragment,
        $privateAccount,
        $privateDomain,
        $userRoot,
        $appsRoot
    )
    $historicalLiterals += $mailDomains | ForEach-Object { "@" + $_ }
    $failures = [System.Collections.Generic.List[string]]::new()

    foreach ($relativePath in $candidateFiles) {
        if ($forbiddenExtension.IsMatch($relativePath)) {
            $failures.Add("forbidden content extension: $relativePath")
            continue
        }
        foreach ($pattern in $forbiddenText) {
            if ($pattern.IsMatch($relativePath)) {
                $failures.Add("private identifier pattern in path: $relativePath")
                break
            }
        }

        $path = Join-Path $repositoryRoot $relativePath
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            continue
        }

        $bytes = [System.IO.File]::ReadAllBytes($path)
        if ($bytes.Length -ge 4 -and
            $bytes[0] -eq 0x4e -and $bytes[1] -eq 0x45 -and
            $bytes[2] -eq 0x53 -and $bytes[3] -eq 0x1a) {
            $failures.Add("NES image signature: $relativePath")
            continue
        }
        if ($bytes -contains 0) {
            continue
        }

        $text = [System.Text.Encoding]::UTF8.GetString($bytes)
        foreach ($pattern in $forbiddenText) {
            if ($pattern.IsMatch($text)) {
                $failures.Add("private identifier pattern: $relativePath")
                break
            }
        }
    }

    if ($IncludeHistory) {
        [string[]]$historySelector = if ($HistoryRef) { @($HistoryRef) } else { @("--all") }
        $historyPaths = @(
            git log @historySelector --name-only --pretty=format: |
                Where-Object { $_ } |
                Sort-Object -Unique
        )
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to inspect repository history paths."
        }
        foreach ($historyPath in $historyPaths) {
            if ($forbiddenExtension.IsMatch($historyPath)) {
                $failures.Add("historical forbidden content extension: $historyPath")
            }
            foreach ($pattern in $forbiddenText) {
                if ($pattern.IsMatch($historyPath)) {
                    $failures.Add("private identifier pattern in historical path: $historyPath")
                    break
                }
            }
        }

        $metadata = git log @historySelector --format="%an%n%ae%n%B"
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to inspect repository history metadata."
        }
        foreach ($pattern in $forbiddenText) {
            if ($pattern.IsMatch(($metadata -join "`n"))) {
                $failures.Add("private identifier pattern in commit metadata")
                break
            }
        }

        foreach ($revision in @(git rev-list @historySelector)) {
            foreach ($literal in $historicalLiterals) {
                git grep -I -i -q -F -e $literal $revision --
                if ($LASTEXITCODE -eq 0) {
                    $failures.Add("private identifier pattern in historical tree $revision")
                    break
                }
                if ($LASTEXITCODE -gt 1) {
                    throw "Unable to inspect historical tree $revision."
                }
            }
        }
    }

    if ($failures.Count -gt 0) {
        $failures | Sort-Object -Unique | ForEach-Object { Write-Error $_ }
        throw "Repository public-content audit failed."
    }

    Write-Host "Repository public-content audit passed ($($candidateFiles.Count) candidate files)."
    $global:LASTEXITCODE = 0
}
finally {
    Pop-Location
}
