# Milestone 12: minimal RomM integration

Milestone 12 makes the separate RomM fork the browser control plane for the
already-proven session topology. An authenticated user can open a RomM game page,
create or discover a session, join or leave it, close a session they own, and open
their scoped browser player.

## Boundary

RomM implements a generic external multiplayer session provider. Its browser API
contains only lobby display data and a participant's short-lived player URL/token.
It does not expose Docker, container names, private addresses, RetroArch arguments,
Netplay ports, coturn details, or Selkies master credentials.

The Session Manager calls a separate service-authenticated RomM endpoint to resolve a
numeric RomM ROM ID. RomM looks up its trusted database model, confines the file below
`LIBRARY_BASE_PATH`, rejects missing/physical/escaping paths, and returns only platform,
relative path, and SHA-256 metadata. The Runtime Agent remains the only component with
Docker access and independently enforces the configured ROM root and digest.

RomM's stable OIDC username can be a 64-character hashed subject, while RetroArch's
Netplay nickname wire field permits only 31 content bytes plus its terminator. The
Session Manager therefore preserves short display names but maps longer names to the
session-local `Player 1` / `Player 2` slot name before launching RetroArch. Failed or
departed guest attempts do not consume the user's right to retry joining an open
session. Open sessions remain discoverable at full capacity so both participating
RomM pages continue renewing their leases and retain access to **Open player**; the UI
disables **Join** for non-participants while a room is full.

The RomM extension remains in the AGPL fork at `<separate-romm-worktree>` on branch
`feat/external-multiplayer-provider`. No RomM source is copied into this repository.

## Local proof

The overlay combines the accepted Milestone 10 runtime stack and Milestone 11
authentik/RomM stack behind one Traefik origin. The local proof deliberately uses
`http://localhost:8096`: browsers treat localhost as a trustworthy origin, so Selkies'
secure-context requirement is met without a locally trusted certificate. A LAN or
public deployment still requires trusted HTTPS.

```powershell
.\infra\scripts\acceptance\milestone12-start.ps1 -RomMSource <separate-romm-worktree>
.\infra\scripts\acceptance\milestone12-verify.ps1
```

The start helper builds digest-addressed local RomM and runtime images, creates ignored
credentials, copies the ignored test ROM into RomM's expected `nes/roms` library
layout, and starts the composed stack. In RomM, scan the NES platform, open the game,
and use the **Multiplayer sessions** card. Keep the RomM page open while playing so it
can renew the participant lease.

Stop the proof without deleting the named identity/database volumes:

```powershell
.\infra\scripts\acceptance\milestone12-stop.ps1
```

Only the proven NES/Mesen runtime profile is supported in this milestone. SNES and
other console profiles remain explicitly deferred to later milestones.

## Verification

Automated checks cover private provider authentication, unsafe upstream URLs, bounded
JSON handling, trusted relative ROM path resolution, locale parity, frontend types,
and compose security boundaries. The live verifier checks the common RomM origin, the
private service-authenticated game resolver, and confirms Session Manager has no
Docker socket mount.

Manual acceptance passed on 2026-09-07 with two authenticated browser users. One user
created the session, the other joined it, and **Open player** launched both separately
authorized Selkies screens. Both streams remained active and displayed synchronized
gameplay responding to controller input. This satisfies the Milestone 12 exit criterion.

### Two-user browser acceptance

First complete RomM's one-time setup wizard, scan the detected NES platform, and wait
for the imported game to appear. The wizard's administrator is a local emergency RomM
account; it is separate from the two authentik test identities.

1. Open `http://localhost:8096/login` in two independent browser cookie
   jars—for example, Edge InPrivate for player one and Chrome Incognito for player
   two, or two named browser profiles. Two private windows from the same browser may
   share cookies and are not sufficient.
2. In profile A, choose the authentik/OIDC login and enter the value of
   `M11_TEST_USER_A_EMAIL` from ignored `.env.milestone12`. Open Mailpit at
   `http://127.0.0.1:8025`, open that user's newest message, copy the sign-in link,
   and paste it into profile A.
3. Repeat in profile B with `M11_TEST_USER_B_EMAIL`, opening that user's link in
   profile B. Confirm RomM shows two different signed-in users.
4. In both profiles, open the same imported NES game's details page. Keep both game
   pages open; they renew each participant's lease every ten seconds.
5. In profile A's **Multiplayer sessions** card, enter a session name and choose
   **Create session**. Its row should show **1 of 2 players** and offer
   **Open player**.
6. In profile B, wait up to ten seconds for the row to appear (or reload the game
   page), then choose **Join**. Both profiles should show **2 of 2 players**, and
   profile B should now offer **Open player**.
7. Allow pop-ups for the arcade origin, then choose **Open player** once in each
   profile. Each action opens that user's separately authorized browser player. Leave
   the original RomM game pages open while testing.
8. Confirm both players load the NES game and can provide independent input. When
   finished, close the player tabs, choose **Leave** for player B, and choose
   **Close** for the owner in profile A.

If authentik reports an unknown email, rerun `milestone12-start.ps1`; the helper now
creates the two test identities idempotently. If no player tab opens, allow pop-ups
for `localhost:8096` and try **Open player** again. Do not substitute the old
`arcade.127.0.0.1.nip.io` URL: despite resolving to loopback, browsers do not grant
that HTTP hostname localhost's secure-context exception.

If a session was created before the Netplay nickname fix, close that session and
create a new one; its failed participant history is intentionally retained in the old
session record. After rebuilding or restarting the stack, reload both RomM tabs before
starting the acceptance flow.
