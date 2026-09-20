# Authentication login failure

## Trigger

authentik login, email authentication, OIDC callback, or RomM session establishment fails.

## Diagnose

1. Record UTC time, browser-visible correlation details, and HTTP status without cookies,
   codes, state values, or credentials.
2. Check authentik server/worker and RomM health and structured logs.
3. Verify public issuer, exact redirect URI, certificate validity, and SMTP delivery.
4. Confirm the stable OIDC `sub` mapping remains configured; email is not the identity key.

## Recover

Correct the authentik provider/flow, DNS/TLS, or SMTP dependency and retry in a fresh
private window. Preserve the documented emergency local administrator path. Do not add a
Session Manager login database or weaken callback/state/nonce validation.
