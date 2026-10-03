# Contributing to Folionym

Thanks for taking a look. This guide covers setup, the checks we run, and the
data-handling rules that keep the project safe to work on. Participation is
covered by the [Code of Conduct](CODE_OF_CONDUCT.md).

## Development setup

Folionym requires CPython 3.14; the repository and CI use 3.14.6. Install all
Python extras and the frontend dependencies with:

```bash
make install-dev
```

## Architecture

Read [DESIGN.md](DESIGN.md) before you change package boundaries, data flow, or
apply semantics. `rename_ops` is the filesystem mutation boundary described by
[ADR 0001](docs/decisions/0001-rename-filesystem-boundary.md); the package
structure and shared reviewed-plan contract are described by
[ADR 0002](docs/decisions/0002-modular-monolith-boundaries.md) and refined by
[ADR 0003](docs/decisions/0003-responsibility-based-module-boundaries.md).

Where new code belongs is listed in the
[DESIGN.md](DESIGN.md#where-new-code-belongs) section of that name. The
allowed package dependencies are the `ALLOWED_DEPENDENCIES` allowlist in
`scripts/check_architecture.py`; a new cross-package import requires editing that
allowlist in the same change, and `make architecture-check` fails without it.

Keep the public facades `folionym.config`, `folionym.filename`,
`folionym.heuristics`, `folionym.renamer`, and `folionym.rename_ops`. Put
interface adaptation in `interfaces/` and low-level primitives in
`infrastructure/`, and keep application orchestration out of both. Do not add
new compatibility re-exports without a documented public requirement.

The test layout mirrors those boundaries:

| Path | Scope |
| --- | --- |
| `tests/contracts/` | the public surface: facades, console entry points, configuration precedence and file formats, persisted exports, and the web HTTP API |
| `tests/workflows/` | end-to-end user workflows: CLI dry run, apply and undo, interactive prompts, browser preview to apply, rendered TUI flows, and real-PDF proposals |
| `tests/<package>/` | focused behavior owned by one package: `settings`, `naming`, `llm`, `extraction`, `rename_ops`, `application`, `infrastructure`, and `interfaces` |
| `tests/tooling/` | the repository scripts in `scripts/` |

Shared fixtures (real synthetic PDFs, a fake PyMuPDF module, an in-process ASGI
client, an isolated home) live in `tests/conftest.py`. Name test files after the
behavior or owner they cover, never after the change that introduced them.

## Change workflow

1. Reproduce the behavior or failure at the boundary that owns it.
2. Make the smallest change that keeps public contracts and safety policy intact.
3. Add or adjust behavioral tests in the relevant test area.
4. Run the narrowest relevant check, then the release gate for release-ready work.

```bash
make format
make lint
make typecheck
make test
make architecture-check
make frontend-check
make release-check
make ci
```

`make format` modifies Python files. `make frontend-check` runs the Node tests,
type-checks the browser source, and rebuilds the packaged assets in
`src/folionym/web_dist/`. `make release-check` includes dependency-lock
validation, the frontend build, repository hygiene, the architecture check,
Ruff, strict mypy, tests, package builds, and installed-wheel verification.
Before handoff, `make lint typecheck test architecture-check` and
`make frontend-check` should pass. `make ci` runs what CI runs: the browser smoke
check, `make release-check`, and `make web-dist-check`. Run
`make web-dist-check` after frontend changes; it rebuilds the bundle and fails if
`src/folionym/web_dist/` differs from the committed assets.

For frontend work, run the following from `frontend/` as appropriate:

```bash
npm run typecheck
npm test
npm run test:browser
npm run dev
npm run build
npm run build:demo
```

The normal build writes the packaged assets; the demo build writes ignored
`dist-demo/`. See [docs/frontend.md](docs/frontend.md) for the difference.

## Standards and sensitive data

- Target Python 3.14, keep Ruff and strict mypy passing, and write user-facing
  documentation in direct technical language.
- Keep unrelated formatting and refactoring out of a change. Do not commit,
  push, tag, or publish unless explicitly authorized.
- Do not commit PDFs, extracted content, filenames, paths, metadata, model
  bodies, logs, caches, exports, backups, credentials, tokens, or local state.
- Add runtime dependencies only with maintainer agreement, and follow
  [SECURITY.md](SECURITY.md) for transport and vulnerability reporting.

The browser smoke command uses an installed Chromium executable, discovered
locally or supplied through `FOLIONYM_BROWSER`, with an isolated temporary
profile. The Python tests include rendered Textual workflows at compact and
desktop terminal sizes. No real documents or model endpoint are required.

For local compatibility checks on a different installed Python 3.14 patch, set
`UV_PYTHON` and `PYTHON_VERSION` for Make. The default and CI release interpreter
remain 3.14.6.
