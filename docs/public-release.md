# Public release hygiene

The repository is source-only. ROMs, BIOS files, save data, emulator states,
credentials, personal identifiers, machine-specific paths, and production endpoint
names must remain outside Git.

Before publishing, run:

```powershell
./tools/repository-audit/verify-public.ps1 -IncludeHistory
```

The audit examines tracked and unignored files, common game-content extensions, an NES
image signature, selected private-identifier patterns, commit metadata, historical
paths, and historical text. The Security workflow also scans the full Git history with
a digest-pinned Gitleaks image. These checks do not replace manual review or credential
rotation after a leak.

Keep local game libraries and runtime state under ignored `local/` paths or, preferably,
outside the repository. Use only redistributable homebrew content for testing and fetch
it with the documented helper rather than committing it.

When a prohibited artifact or identifier has entered Git history, removing it from the
current tree is insufficient. Prepare a clean history, verify it independently, and
coordinate any required force-push with collaborators.

The neutral public namespace is `retrobrowser`. Adopting it changes container image
names, Docker labels and networks, the control socket path, metrics, and state-key
prefixes. Stop the old deployment before upgrading and deliberately migrate any
persistent save data; do not expect an in-place mixed-namespace deployment to work.
