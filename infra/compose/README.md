# Compose layouts

The supported deployment model is the repository-root `compose.yml`. It is the
single production topology and is operated through `infra/scripts/production`.

`acceptance/` contains milestone proof and regression layouts. Those files are
development/acceptance fixtures, may require several overlays, and are not a
supported deployment interface.
