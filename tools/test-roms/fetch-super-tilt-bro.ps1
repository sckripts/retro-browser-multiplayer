[CmdletBinding()]
param(
    [string]$Destination
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
if ([string]::IsNullOrWhiteSpace($Destination)) {
    $Destination = Join-Path $repoRoot "local/test-roms/super-tilt-bro-2.6.nes"
}

$expectedSha256 = "847155bb712e474f71554174c9d9ed402bf651b13ff1e4afc9a42ec69cd03d8d"
$gamePageUri = "https://sgadrat.itch.io/super-tilt-bro"
$uploadId = "16311760"
$session = [Microsoft.PowerShell.Commands.WebRequestSession]::new()

$page = Invoke-WebRequest -UseBasicParsing -WebSession $session -Uri $gamePageUri
$csrfMatch = [regex]::Match($page.Content, 'name="csrf_token" value="([^"]+)"')
if (-not $csrfMatch.Success) {
    throw "itch.io did not provide the expected CSRF token"
}
$csrfToken = $csrfMatch.Groups[1].Value

$downloadInfo = Invoke-RestMethod `
    -UseBasicParsing `
    -WebSession $session `
    -Method Post `
    -Uri "$gamePageUri/file/$uploadId`?source=view_game&as_props=1" `
    -Headers @{ "X-CSRFToken" = $csrfToken; "X-Requested-With" = "XMLHttpRequest" } `
    -Body @{ csrf_token = $csrfToken }

if ([string]::IsNullOrWhiteSpace($downloadInfo.url)) {
    throw "itch.io did not return a download URL for upload $uploadId"
}

$destinationPath = [IO.Path]::GetFullPath($Destination)
$destinationDirectory = Split-Path -Parent $destinationPath
New-Item -ItemType Directory -Force -Path $destinationDirectory | Out-Null
$temporaryPath = "$destinationPath.download"

try {
    Invoke-WebRequest -UseBasicParsing -OutFile $temporaryPath -Uri $downloadInfo.url
    $actualSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $temporaryPath).Hash.ToLowerInvariant()
    if ($actualSha256 -ne $expectedSha256) {
        throw "Downloaded ROM SHA-256 mismatch: expected $expectedSha256, got $actualSha256"
    }
    Move-Item -Force -LiteralPath $temporaryPath -Destination $destinationPath
}
finally {
    if (Test-Path -LiteralPath $temporaryPath) {
        Remove-Item -LiteralPath $temporaryPath
    }
}

Write-Host "Fetched verified Super Tilt Bro 2.6 to $destinationPath"
Write-Host "SHA-256: $expectedSha256"
Write-Host "The ROM remains ignored by Git and excluded from Docker build contexts."
