# Milestone 11 — authentik and RomM OIDC

## Status

Accepted on 2026-09-06. Two distinct users completed repeated browser sign-ins and the
strict RomM-row verifier passed. Milestone 12 has not started.

## Implemented behavior

- Pinned authentik 2026.8.1 server and worker with private PostgreSQL.
- No Docker socket on authentik, RomM, or any supporting service.
- Generated credentials in ignored `.env.milestone11`.
- Preserved `akadmin` as the emergency local identity administrator.
- Provisioned two active local test identities with distinct authentik UIDs.
- Configured a ten-minute, enumeration-resistant email magic-link flow through local
  Mailpit SMTP.
- Configured a confidential RomM OIDC authorization-code provider with an exact
  callback, a per-provider issuer, signed tokens, and a hashed `sub`.
- Configured RomM 5.2.0 to create OIDC users with `sub` as their username while leaving
  OIDC autologin disabled for emergency local RomM access.
- Started RomM with empty named library and asset volumes; no ROM or BIOS data is used.

## Automated evidence

Live Docker Desktop validation on 2026-09-06 proved all six services healthy, the
blueprint applied, OIDC discovery returned the expected per-provider issuer, the two
test users had distinct stable authentik UIDs, and RomM initiated a state- and
nonce-bound authorization-code request to the exact authentik endpoint. The static
callback is strict, and the same browser-visible discovery URL is reachable from
inside the RomM container. The static integration tests also enforce immutable image
references, loopback-only published
ports, absence of Docker-socket mounts, exact callback matching, and stable-subject
configuration.

RomM 5.2.0 is a confidential client but does not send PKCE parameters. This document
records that upstream behavior; the flow still uses authorization code, state, nonce,
an exact callback, and a client secret.

## Browser acceptance

Two separate browser profiles signed in as the two local test users through authentik
email links. Each user then repeated the OIDC login. The strict verifier passed:

```powershell
.\infra\scripts\acceptance\milestone11-verify.ps1 -RequireRomMUsers
```

The check found exactly two matching RomM rows, each with the expected 64-character
hexadecimal form of authentik's hashed provider-scoped subject as its stored username.
The repeated logins created no duplicate row, satisfying the Milestone 11 exit
criterion.

RomM 5.2.0 looks up returning OIDC users by email. Its database ID remains stable while
the email is stable, but changing the authentik email can create a second account.
Correcting that upstream limitation belongs in the separate AGPL RomM fork; this
repository does not copy or modify RomM code.

For commands, credentials, local URLs, cleanup semantics, and production hardening,
see `docs/deployment.md` and `docs/authentication.md`.
