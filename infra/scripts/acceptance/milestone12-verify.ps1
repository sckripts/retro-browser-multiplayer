[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$environmentFile = Join-Path $repositoryRoot ".env.milestone12"
$settings = @{}
Get-Content -LiteralPath $environmentFile | ForEach-Object {
    if ($_ -match '^([^#=]+)=(.*)$') { $settings[$Matches[1]] = $Matches[2] }
}

$heartbeat = Invoke-WebRequest -Uri "$($settings.M12_ROMM_URL)/api/heartbeat" -TimeoutSec 10
if ($heartbeat.StatusCode -ne 200) { throw "RomM heartbeat failed" }

$headers = @{ Authorization = "Bearer $($settings.M11_BOOTSTRAP_TOKEN)" }
$provider = Invoke-RestMethod `
    -Uri "http://127.0.0.1:9000/api/v3/providers/oauth2/?name=Retro%20Arcade%20RomM%20OIDC" `
    -Headers $headers -TimeoutSec 10
$expectedCallback = "$($settings.M12_ROMM_URL)/api/oauth/openid"
if ($provider.pagination.count -ne 1 -or
    $provider.results[0].redirect_uris.Count -ne 1 -or
    $provider.results[0].redirect_uris[0].matching_mode -ne "strict" -or
    $provider.results[0].redirect_uris[0].url -ne $expectedCallback) {
    throw "authentik's RomM callback does not match the Milestone 12 browser origin"
}

$providerHealth = docker exec retro-browser-milestone12-session-manager-1 python -c `
    "import os,urllib.request; r=urllib.request.Request('http://romm:8080/api/multiplayer/health', headers={'X-External-Multiplayer-Token':os.environ['SESSION_MANAGER_ROMM_SERVICE_TOKEN']}); print(urllib.request.urlopen(r, timeout=5).status)"
if ($LASTEXITCODE -ne 0 -or $providerHealth -ne "200") {
    throw "The private RomM game resolver is unavailable"
}

$socketMounts = docker inspect retro-browser-milestone12-session-manager-1 `
    --format "{{range .Mounts}}{{println .Source}}{{end}}"
if ($socketMounts -match "docker.sock") { throw "Session Manager has Docker socket access" }

Write-Host "Milestone 12 service boundaries and private RomM resolver are healthy."
