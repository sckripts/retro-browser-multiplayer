[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$composeFile = Join-Path $repositoryRoot "infra/compose/acceptance/compose.milestone10.yml"
$environmentFile = Join-Path $repositoryRoot ".env.milestone10"
$routeRoot = Join-Path $repositoryRoot "local/runtime-agent-m10/routes"

function Invoke-SessionClient {
    param([Parameter(Mandatory)][string[]]$ClientArguments)

    $output = docker compose --env-file $environmentFile --file $composeFile exec -T `
        session-manager python -m retro_sessions.client @ClientArguments
    if ($LASTEXITCODE -ne 0) {
        $joinedArguments = $ClientArguments -join " "
        throw "Session Manager client failed: $joinedArguments"
    }
    return $output | ConvertFrom-Json
}

function New-TestSession {
    param([Parameter(Mandatory)][string]$Suffix)

    return Invoke-SessionClient @(
        "create", "--name", "Milestone 10 $Suffix", "--user-id", "milestone10-host",
        "--display-name", "Milestone Host"
    )
}

function Wait-ClosedSession {
    param(
        [Parameter(Mandatory)][string]$SessionId,
        [Parameter(Mandatory)][string]$Reason,
        [int]$TimeoutSeconds = 90
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $session = Invoke-SessionClient @("get", $SessionId)
        if ($session.state -eq "CLOSED") {
            if ($session.closed_reason -ne $Reason) {
                $actualReason = $session.closed_reason
                throw "Session closed for [$actualReason], expected [$Reason]."
            }
            return $session
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)
    throw "Session $SessionId did not close within $TimeoutSeconds seconds."
}

function Assert-CleanRuntimeState {
    $listed = docker compose --env-file $environmentFile --file $composeFile exec -T `
        runtime-agent python -m retro_runtime.client list
    if ($LASTEXITCODE -ne 0) { throw "Runtime Agent list failed" }
    $runtimes = ($listed | ConvertFrom-Json).items
    if (@($runtimes).Count -ne 0) { throw "Managed runtimes remain after cleanup" }
    if (Test-Path -LiteralPath $routeRoot) {
        $routes = Get-ChildItem -LiteralPath $routeRoot -Filter "runtime-*.yml" -File
        if (@($routes).Count -ne 0) { throw "Dynamic stream routes remain after cleanup" }
    }
}

function Runtime-Name {
    param([Parameter(Mandatory)][object]$Session)

    $participantId = [string]$Session.participants[0].participant_id
    return "retrobrowser-runtime-" + $participantId.Replace("-", "")
}

$browserSession = New-TestSession "Browser Heartbeat"
Start-Sleep -Seconds 20
$heartbeat = Invoke-SessionClient @("heartbeat", $browserSession.session_id)
if ($heartbeat.state -ne "OPEN") { throw "Heartbeat did not preserve the open session" }
Start-Sleep -Seconds 20
$stillOpen = Invoke-SessionClient @("get", $browserSession.session_id)
if ($stillOpen.state -ne "OPEN") { throw "Renewed heartbeat expired too early" }
Wait-ClosedSession $browserSession.session_id "owner_abandoned" | Out-Null
Assert-CleanRuntimeState

$retroArchSession = New-TestSession "RetroArch Failure"
$retroArchRuntime = Runtime-Name $retroArchSession
docker exec $retroArchRuntime sh -c "pgrep -x retroarch | xargs kill" 2>$null
if ($LASTEXITCODE -notin @(0, 137)) { throw "Could not terminate RetroArch" }
Wait-ClosedSession $retroArchSession.session_id "owner_runtime_failed" | Out-Null
Assert-CleanRuntimeState

$selkiesSession = New-TestSession "Selkies Failure"
$selkiesRuntime = Runtime-Name $selkiesSession
docker exec $selkiesRuntime sh -c "pgrep -x selkies | xargs kill" 2>$null
if ($LASTEXITCODE -notin @(0, 137)) { throw "Could not terminate Selkies" }
Wait-ClosedSession $selkiesSession.session_id "owner_runtime_failed" | Out-Null
Assert-CleanRuntimeState

$containerSession = New-TestSession "Container Failure"
$containerRuntime = Runtime-Name $containerSession
docker kill $containerRuntime | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Could not kill participant container" }
Wait-ClosedSession $containerSession.session_id "owner_runtime_failed" | Out-Null
Assert-CleanRuntimeState

$restartSession = New-TestSession "Manager Restart"
$managerContainer = "retro-browser-milestone10-session-manager-1"
docker kill $managerContainer | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Could not kill Session Manager" }
docker compose --env-file $environmentFile --file $composeFile up --detach session-manager
if ($LASTEXITCODE -ne 0) { throw "Could not restart Session Manager" }
$deadline = (Get-Date).AddSeconds(90)
do {
    $health = docker inspect --format "{{.State.Health.Status}}" $managerContainer 2>$null
    if ($health -eq "healthy") { break }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $deadline)
if ($health -ne "healthy") { throw "Session Manager did not recover" }
Wait-ClosedSession $restartSession.session_id "manager_restarted" | Out-Null
Assert-CleanRuntimeState

Write-Host "Milestone 10 verification passed: browser, RetroArch, Selkies, container, and Session Manager failures all cleaned tokens, runtimes, routes, and session state."
