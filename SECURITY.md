# Security Policy

## Reporting

Do not open public issues containing credentials, tokens, private network details, or exploitable vulnerability instructions. Until a private reporting address is published, contact the repository owner privately through the GitHub account that hosts the project.

## Current support

The project is pre-release. Only the latest `main` branch is maintained.

## Hard boundaries

- No public Docker API or Docker socket outside Runtime Agent.
- No browser-supplied filesystem paths.
- No public raw Selkies runtime ports or master tokens.
- No committed secrets, ROMs, BIOS files, saves, or runtime route files.
- ROM mounts are read-only; all identifiers and mounts are allowlisted.
- Authentication belongs to authentik, not custom password code.

See `docs/security-boundaries.md` for the full trust model.
