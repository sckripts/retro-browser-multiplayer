# ADR 0006: authentik identity provider

- Status: Accepted
- Date: 2026-08-29

## Decision

authentik owns local authentication, passwordless flows, and future federation. RomM consumes authentik through OIDC and stable subject identifiers.

## Consequences

The project implements no password database, reset flow, OTP cryptography, OAuth server, OIDC provider, or SAML provider.
