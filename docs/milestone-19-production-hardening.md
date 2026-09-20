# Milestone 19: Production hardening

Milestone 19 is **in progress**. This first slice establishes enforceable admission,
resource, edge, audit, and supply-chain controls while preserving the existing service
boundaries.

## Implemented foundation

- Session Manager admits at most four active sessions and one active participant
  runtime per stable user in the production overlay. Global Runtime Agent capacity
  remains eight. All three values are configurable within validated bounds.
- Runtime Agent now consumes explicit memory, CPU, PID, and total-runtime environment
  limits. It still generates these controls itself; the browser and Session Manager
  cannot choose them.
- Successful create, join, leave, launch, kick, and close actions emit structured audit
  events. Stable upstream user IDs are represented by a keyed, rotation-scoped digest;
  tokens, display names, stream URLs, ROM paths, and network details are not logged.
- Public authentik and RomM routes have separate source-IP rate limiting and bounded
  request buffering. Oversized requests receive HTTP 413 before reaching either app.
  Authenticated save/state endpoints use a separate 32 MiB bound and lower concurrency
  and request-rate limits so legitimate cartridge saves are not blocked by the generic
  1 MiB API ceiling.
- Experimental solo EmulatorJS cartridge-save synchronization remains feature-gated
  off after live testing proved upload but not clean relaunch restoration. Native play
  continues to use EmulatorJS's browser-local saves; multiplayer host saves remain
  owned by Runtime Agent.
- HSTS preload and Permissions Policy are enforced. A conservative CSP is initially
  report-only so real authentik, RomM, and embedded-player traffic can be inventoried
  before enforcement without disrupting browser-only access.
- The Security workflow creates CycloneDX JSON SBOM artifacts for the repository and
  all three project-owned images, then scans locked source dependencies and images.
  Fixable High or Critical findings fail the workflow. Third-party actions are pinned
  to immutable commits.

The edge limits are coarse abuse protection, not identity-aware authentication policy.
authentik remains responsible for account and flow controls, and coturn retains its
existing short-lived credentials, unauthorized-request throttling, allocation quotas,
bandwidth ceiling, and bounded relay range.

## Start and verify

Start only from the accepted clean Milestone 18 public stack:

```powershell
infra/scripts/acceptance/milestone19-start.ps1
infra/scripts/acceptance/milestone19-verify.ps1 -RequireRomMUsers -RequireClean
```

The start helper verifies the clean baseline, rebuilds the participant runtime and the
separate AGPL RomM fork, replaces the static public route with the hardening policy, and
upgrades the custom services.
It does not print credentials. Run the Security workflow for the authoritative SBOM and
vulnerability evidence; workflow artifacts are retained for 30 days.

The initial live control-plane upgrade passed on 2026-09-15 with both existing RomM
users, zero participant runtimes, clean generated routes/metrics targets, healthy
services, the CSP and Permissions Policy response headers, and HTTP 413 rejection of an
oversized RomM request. Full two-browser and quota acceptance remains outstanding.

The solo-save extension was initially deployed on 2026-09-16. Live testing on
2026-09-19 found that a 20-second completed SRAM flush uploaded a non-empty 8 KiB save
successfully and produced the expected browser notification, but the save did not
restore on a clean relaunch. The five-minute/two-sample predecessor also allowed an
exit-time request to be canceled with HTTP 499. Automatic server sync is therefore
disabled pending redesign; EmulatorJS browser-local saves are the accepted interim
behavior. The dedicated 32 MiB save route remains tested for future use.

## Acceptance for this slice

1. **Passed 2026-09-19.** With one healthy lobby/runtime active, the same account tried
   to create a lobby for a different game. RomM reported `per-user runtime capacity is
   exhausted`; Session Manager recorded the request as a conflict, and Runtime Agent
   still listed exactly one runtime with capacity use unchanged at 1/8.
2. **Deferred 2026-09-19.** Live confirmation that a fifth concurrent lobby is rejected
   at the production session capacity of four requires five distinct authenticated
   users because the per-user runtime limit is one. Only two test logins are currently
   available. The automated capacity tests remain in place, but this is not live
   acceptance evidence. Re-run this validation when five production/test identities
   are available; investigate and correct the admission policy if more than four active
   sessions are ever admitted.
3. **Passed 2026-09-19.** After the Milestone 19 upgrade, an authenticated user browsed
   the library, created a lobby, loaded moving game video in RomM's embedded player, and
   confirmed responsive directional/action controller input. Chromium WebRTC diagnostics
   showed a selected candidate pair containing a `relay` candidate. At the same time,
   coturn was healthy and Prometheus reported two allocations with bidirectional TURN
   traffic. No stream URL, token, address, credential, or relay port was recorded.
4. **Passed 2026-09-19.** Synthetic unauthenticated controls below the limit reached
   authentik and RomM and returned HTTP 403. Requests one byte above the authentik
   64 KiB and general RomM 1 MiB limits returned HTTP 413. A streamed request one byte
   above the save/state 32 MiB limit also returned HTTP 413. Traefik identified the
   corresponding buffering middleware for all three rejections, while RomM logged only
   the below-limit controls, confirming oversized bodies did not reach the application.
   No credentials or ROM/save content was used.
5. **Passed 2026-09-19.** Report-only CSP was exercised on both public origins.
   authentik required no broad script, worker, connection, or media exceptions. RomM's
   pinned EmulatorJS runtime reported its expected blob worker/script/connection and
   WebAssembly evaluation requirements, so RomM received a separate policy limited to
   those capabilities. During the test, authentik's shared rate limit returned HTTP 429
   for parallel static chunks; `/static/` now has a separately bounded higher-rate
   router, while authentication and API traffic retain the lower limit. Fifty parallel
   static requests subsequently returned HTTP 200 and login succeeded. Native emulation
   was also verified at normal speed on the local client. Apparent slow frames and
   choppy audio reproduced only while observing client-rendered play through Remote
   Desktop; disabling save sync, removing RomM's report-only CSP, and using the prior
   RomM image made no difference, confirming that symptom was a test-environment
   artifact rather than a deployed regression.
6. **Passed 2026-09-19.** Eight live lifecycle audit records covered session creation,
   stream launch, participant leave, and session close. Every record contained an
   action, outcome, 24-character pseudonymous actor ID, and session ID. Structured
   inspection found no credential, authorization token, raw user ID/subject, stream
   URL, ROM path, or network field. The focused automated pseudonymization test also
   passed.
7. **Passed 2026-09-19.** Session discovery returned zero active lobbies, no participant
   runtime container remained, and the strict verifier passed with both
   `-RequireRomMUsers` and `-RequireClean`. This also revalidated the public boundary,
   pinned SNES and Genesis cores, persistence, observability configuration, runtime
   resource settings, edge controls, CSP/Permissions Policy headers, request bounds,
   and the intentionally disabled pending-acceptance RomM cartridge-save feature flag.

## Remaining work

This slice does not complete Milestone 19. The next hardening work must include:

- documented and exercised secret rotation, including overlap/rollback semantics;
- configuration, Valkey, PostgreSQL, authentik media, RomM database/configuration, and
  host-authoritative save backup policy plus a clean-machine restore test;
- SMTP provider-side send limits and authentik recovery/enrollment abuse testing;
- an encoder-specific admission limit distinct from general runtime capacity;
- security review findings and threat-model sign-off;
- vulnerability triage/exception/response ownership and release blocking policy;
- CSP enforcement after report-only acceptance;
- disaster-recovery objectives and evidence;
- a public-source/license obligation check for every deployed RomM fork build.
- redesign and end-to-end acceptance of solo cartridge-save server synchronization,
  including interrupted-upload retry and clean relaunch restoration;

No ROMs, BIOS images, save contents, credentials, or generated SBOM artifacts belong in
Git.
