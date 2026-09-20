# authentik

Milestone 11 deploys authentik from the pinned upstream image and loads
`blueprints/milestone11-romm.yaml`. The blueprint contains no credentials: client
credentials and callback URLs are read from the worker environment with authentik's
`!Env` tag.

The RomM provider uses a confidential authorization-code client, an exact callback,
per-provider issuer, hashed stable subject, signed tokens, and only the `openid`,
`profile`, and verified-email mappings. Its authentication flow sends a ten-minute
magic link and uses enumeration-resistant identification. Production must replace the
local Mailpit SMTP sink and HTTP proof URLs with real SMTP and HTTPS settings.

Neither authentik service receives the Docker socket. The emergency `akadmin`
credential and all local proof secrets are generated into ignored
`.env.milestone11`.
