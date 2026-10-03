# Folionym documentation

Start with the [README](../README.md) for installation, configuration, command
examples, and operational limits. The pages below go deeper.

## Using Folionym

- [Browser interface](frontend.md): the loopback Source, Preview, and exact
  Apply flow, plus the simulated static demo.
- [Terminal interface](tui.md): Textual directory plans and immediate
  single-file rename.
- [Resource limits and performance](performance.md): extraction, cache, model,
  image, and browser limits and how they are verified.

## Understanding the design

- [Architecture](../DESIGN.md): system context, components, dependency
  direction, runtime flows, state, and invariants.
- [Product scope](../PRODUCT.md): supported workflows and interface
  requirements.
- [Decision 0001](decisions/0001-rename-filesystem-boundary.md): the filesystem
  mutation boundary.
- [Decision 0002](decisions/0002-modular-monolith-boundaries.md): package
  boundaries and the shared reviewed-plan contract.
- [Decision 0003](decisions/0003-responsibility-based-module-boundaries.md):
  responsibility-based module ownership enforced as an allowlist.

## Project and releases

- [Security policy](../SECURITY.md): trust boundaries and private reporting.
- [Contribution guide](../CONTRIBUTING.md): development setup, checks, and data
  handling.
- [Release process](../RELEASING.md): clean-checkout verification and authorized
  prerelease publication.
- [Support](../SUPPORT.md): where to get help and how to report a problem.
- [Code of conduct](../CODE_OF_CONDUCT.md): community expectations.
- [0.4.0a1 notes](releases/0.4.0a1.md): alpha installation and limitations.
- [Changelog](../CHANGELOG.md): version history.
