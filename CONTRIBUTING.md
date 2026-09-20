# Contributing

Read `PROJECT.md` and `AGENTS.md` before making changes. Work on one milestone or coherent change per branch, add tests with behavior changes, and keep upstream code outside this repository.

Before submitting a change, run:

```text
ruff check .
ruff format --check .
mypy services
pytest
```

Never commit secrets, commercial ROMs, BIOS images, generated routes, active tokens, or copied upstream source trees. Update `UPSTREAMS.md` and notices whenever a dependency changes. Architectural or security-boundary changes require an ADR.

Run `./tools/repository-audit/verify-public.ps1` before committing and add
`-IncludeHistory` before publishing a branch. See `docs/public-release.md` for the
repository release policy.

Original contributions are accepted under Apache-2.0 unless explicitly documented otherwise.
