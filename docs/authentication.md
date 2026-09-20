# Authentication

authentik is the identity provider. RomM is an OIDC relying party. Session Manager
trusts only authenticated, service-to-service requests from RomM and does not store or
validate passwords.

Milestone 11 configures RomM 5.2.0 with `OIDC_USERNAME_ATTRIBUTE=sub`. authentik's
provider uses `hashed_user_id`, so the RomM username created at first login is the
provider-scoped stable OIDC subject rather than a mutable display name. Two users may
share neither an email nor a subject.

There is an upstream limitation to keep explicit: RomM 5.2.0 locates an existing OIDC
account by email before using the configured username claim. A normal repeated login
with a fixed verified email retains one database row and ID, but changing the email at
the identity provider can create a different RomM account. Fixing that behavior belongs
in the separate AGPL RomM fork and is not part of this milestone.

The checked-in authentik blueprint provides email magic-link authentication with a
ten-minute token and enumeration-resistant identification. Only users whose authentik
record has `attributes.email_verified=true` receive a verified email claim accepted by
RomM. The local harness provisions two such test users; production provisioning must
set that attribute only after the address is verified.

The authentik `akadmin` local credential in ignored `.env.milestone11` is the emergency
identity-administration path. RomM OIDC autologin remains disabled so RomM's own local
administrator remains reachable through its login page after initial setup. Keep both
credentials in the deployment secret store, test them after upgrades, and do not use
either for routine play.
