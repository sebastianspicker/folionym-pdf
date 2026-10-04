# Folionym

**Rename PDFs from what's actually inside them — locally, with a review step before anything moves.**

[![CI](https://github.com/sebastianspicker/folionym-pdf/actions/workflows/ci.yml/badge.svg)](https://github.com/sebastianspicker/folionym-pdf/actions/workflows/ci.yml)
[![Security](https://github.com/sebastianspicker/folionym-pdf/actions/workflows/security.yml/badge.svg)](https://github.com/sebastianspicker/folionym-pdf/actions/workflows/security.yml)
[![Pages demo](https://github.com/sebastianspicker/folionym-pdf/actions/workflows/pages.yml/badge.svg)](https://github.com/sebastianspicker/folionym-pdf/actions/workflows/pages.yml)
[![Python 3.14+](https://img.shields.io/badge/python-3.14%2B-3776AB)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-0e6b57)](LICENSE)

Folionym reads the text and metadata of a PDF, works out a useful filename with
deterministic rules and optional local-LLM help, and shows you the result before
touching the filesystem. You can drive it from the command line, a terminal UI,
or a browser UI that only listens on your own machine.

**Try it without installing:** [open the interactive demo](https://sebastianspicker.github.io/folionym-pdf/)
— it runs entirely in your browser on simulated files.

> **Status:** alpha (`0.4.0a1`). Keep backups of important documents and review
> proposed names before applying them.

![Folionym Preview screen with a rename ledger](docs/screenshots/02-preview.png)

## What it does

Given a folder of PDFs, Folionym proposes a name for each one:

```text
YYYYMMDD-category-keywords-summary.pdf
```

It can also build names from a template using date, project, category,
keywords, summary, version, invoice ID, amount, and company fields.

- PDF text and metadata extraction with PyMuPDF
- Heuristic classification using bundled category data
- Optional OCR through OCRmyPDF and optional vision through a compatible model
- OpenAI-compatible HTTP endpoints for summaries, keywords, categories, and vision
- Directory, recursive, single-file, watch, dry-run, and interactive workflows
- Exact reviewed plans in the browser and directory TUI
- Backups, rename logs, constrained undo, plan export, metadata export, and run summaries

Everything runs as one local process under your own user account. The LLM
endpoint and the optional post-rename hook are the only places document-derived
content can leave the machine.

## A quick tour

| Source | Preview |
| --- | --- |
| [![Choose a folder or a single PDF](docs/screenshots/01-source.png)](docs/screenshots/01-source.png) | [![Review proposed names in the ledger](docs/screenshots/02-preview.png)](docs/screenshots/02-preview.png) |
| Pick a folder or a single file and set the naming rules. | Review every proposal, filter by status, and inspect the evidence behind each name. |

| Apply report | Dark theme |
| --- | --- |
| [![Per-file apply report](docs/screenshots/03-apply.png)](docs/screenshots/03-apply.png) | [![Preview in the dark theme](docs/screenshots/04-preview-dark.png)](docs/screenshots/04-preview-dark.png) |
| See exactly what was renamed, skipped, or left unchanged. | A light and dark theme are both included. |

Prefer a hands-on look first? The [static demo](https://sebastianspicker.github.io/folionym-pdf/)
reproduces these screens with simulated documents and never calls the local
backend.

## Requirements

Runtime requirements depend on the features you use:

- CPython 3.14 or later
- PyMuPDF through the `pdf` extra for PDF processing
- An OpenAI-compatible HTTP endpoint when LLM or vision features are enabled
- OCRmyPDF and its platform prerequisites, including Tesseract, when OCR is enabled

Contributors need CPython 3.14.6, [uv](https://docs.astral.sh/uv/), Node.js
22.12 or later, npm, and Make. The pinned Python version and CI version live in
`.python-version` and `.github/workflows/ci.yml`.

## Install from source

Create an isolated environment and install the PDF feature:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[pdf]'
```

Add the interfaces and optional processing features you need:

```bash
python -m pip install -e '.[pdf,tui,web]'
python -m pip install -e '.[pdf,tokens,ocr,tui,web]'
```

| Extra | Adds |
| --- | --- |
| `pdf` | PyMuPDF text, metadata, image, and thumbnail support |
| `tokens` | token-aware content limits through tiktoken |
| `ocr` | OCRmyPDF integration |
| `tui` | Textual terminal interface |
| `web` | FastAPI, Uvicorn, PyMuPDF, and the browser interface |
| `dev` | Python test, lint, format, and type-check tools |

For a contributor checkout, install all Python extras and the locked frontend
dependencies from the repository root:

```bash
make install-dev
```

No package-index publication is configured. If a GitHub prerelease is
available, follow its authored release notes and verify its checksum before
installing the wheel.

## Quick start

Preview a directory without sending content to an LLM:

```bash
folionym --dir ./input_files --no-llm --dry-run
```

Preview a recursive selection:

```bash
folionym --dir ./input_files --recursive --include '*.pdf' \
  --exclude 'draft-*' --dry-run
```

Apply proposals, confirming each file and recording backups and an undo log:

```bash
folionym --dir ./input_files --interactive \
  --backup-dir ./backup --rename-log ./rename.log
folionym-undo --rename-log ./rename.log --dry-run
```

Other entry points:

```bash
folionym-tui
folionym-web
folionym --manual ./input_files/document.pdf
folionym --dir ./input_files --watch --watch-interval 60
folionym --doctor
```

`folionym-web` serves `http://127.0.0.1:8765/source` and opens your default
browser. Use `folionym-web --port 9000 --no-open` to pick another loopback port
without opening a browser. See the [browser guide](docs/frontend.md) and the
[terminal guide](docs/tui.md) for their reviewed workflows, and run
`folionym --help` for the complete CLI option list.

## How renaming stays safe

Folionym has two deliberate apply policies:

- **Unique-available.** Conventional CLI runs and immediate TUI single-file
  renames use a target that is free at the moment of the move. A collision can
  receive a numeric suffix.
- **Exact reviewed.** Browser and directory-TUI plans apply the exact target you
  reviewed. Apply rechecks source identity, selected duplicates, and target
  availability at the filesystem mutation boundary, then fails on a conflict
  instead of quietly choosing another name. On POSIX, backup and copy fallbacks
  continue reading the verified source descriptor rather than reopening its
  pathname.

A few consequences worth knowing:

- CLI dry run and apply are separate invocations and recompute proposals.
  `--plan-file` exports proposals; it is not consumed later as an apply plan.
- Browser plans and reports live only in the running server process. Completed
  runs expire after one hour or when more than 32 are retained; active
  operations pin their inputs. An expired plan needs a new Preview.
- The directory TUI keeps a completed plan until you apply it or a material
  source or settings change invalidates it.

The [architecture guide](DESIGN.md) is the reference for these flows and their
package boundaries.

## Configuration

For the `folionym` CLI, effective values are resolved in this order:

1. explicitly supplied CLI options;
2. supported environment variables;
3. JSON or YAML values loaded with `--config`;
4. a named `--preset` and built-in defaults.

Presets rank below explicit options, environment variables, and the config file.
The five `--preset` values contribute these defaults:

- `scanned`: enables the vision fallback and simple naming mode;
- `high-confidence-heuristic`: skips the LLM category step when the heuristic
  score is at least 0.5 and its gap at least 0.3;
- `fast`: heuristics first, with the LLM off and stricter heuristic thresholds
  (score 0.6, gap 0.25);
- `accurate`: more LLM analysis, with separate LLM calls and permissive
  heuristic thresholds;
- `batch`: four workers and the persistent response cache.

In the browser and TUI, the form always sends every value, so a selected
preset's mode switches (vision fallback and simple naming, LLM on or off,
separate LLM calls, the response cache) take precedence over the form, while
its thresholds and worker count only fill values the form leaves unset.

Configuration files must contain a mapping and use internal configuration key
names:

```yaml
language: en
desired_case: kebabCase
dry_run: true
use_llm: false
workers: 2
max_pages_for_extraction: 20
```

Validate it without processing PDFs:

```bash
folionym --config ./folionym.yaml --dir ./input_files --validate-config
```

The browser and TUI persist their form values in `~/.folionym_ui.json` and pass
the current form as explicit runtime configuration. That UI state is not a CLI
configuration file. An existing `~/.folionym_tui.json` can be migrated without
deleting the old file.

The default LLM preset uses `qwen2.5:3b`; the `gpu` preset selects
`qwen2.5:7b-instruct`. The configured default URL is the completions URL
`http://127.0.0.1:11434/v1/completions`. With the default chat API, requests go
to the derived `/v1/chat/completions` endpoint; `--no-chat-api` uses the
completions endpoint itself, and `--no-json-mode` stops requesting a JSON
response format. Override the endpoint explicitly when needed:

```bash
FOLIONYM_LLM_URL=http://127.0.0.1:11434/v1/completions \
FOLIONYM_LLM_MODEL=qwen2.5:3b \
folionym --dir ./input_files --dry-run
```

| Variable | Purpose |
| --- | --- |
| `FOLIONYM_LLM_URL` | LLM HTTP endpoint |
| `FOLIONYM_LLM_MODEL` | model identifier sent to the endpoint |
| `FOLIONYM_LLM_TIMEOUT` | request timeout in seconds |
| `FOLIONYM_REQUIRE_HTTPS` | reject non-loopback HTTP LLM endpoints when true |
| `FOLIONYM_MAX_TOKENS` | PDF extraction token cap |
| `FOLIONYM_MAX_CONTENT_CHARS` | character cap for LLM input |
| `FOLIONYM_MAX_CONTENT_TOKENS` | token cap for LLM input |
| `FOLIONYM_CACHE_DIR` | persistent LLM response cache directory |
| `FOLIONYM_DATA_DIR` | directory containing the required JSON data files |
| `FOLIONYM_OCR_LANG` | OCR language |
| `FOLIONYM_POST_RENAME_HOOK` | HTTP(S) endpoint called after a rename |
| `FOLIONYM_LOG_FILE` | log file path |
| `FOLIONYM_LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` |
| `FOLIONYM_STRUCTURED_LOGS` | write JSON log records when true |
| `FOLIONYM_USE_VISION_FALLBACK` | enable vision for low-text PDFs when true |
| `FOLIONYM_VISION_FIRST` | try vision before text extraction when true |

`.env.example` is a template only. Folionym does not load dotenv files; export
values in the shell or arrange for a process manager to load them.

The default log path is `~/.local/share/folionym/error.log`, with `./error.log`
as a fallback when the user data directory cannot be used.

## Limits and operating model

- Run one Folionym process per target directory. There is no interprocess lock
  for concurrent writers.
- The browser binds only to loopback and is not a remote or multi-user service.
- Input size has no hard byte limit. Text extraction stops after accumulating
  its token budget; `--full-text-extraction` restores reading all selected pages
  before truncation, and `--max-pages-for-extraction` adds a page limit. Worker
  count has no hard maximum, and OCR has no application-level timeout.
- Model calls use one session by default. Opt in to independent sessions with
  `--llm-concurrency`, bounded by the effective worker count. Cancellation stops
  queued model calls; an in-flight request still runs until it finishes or times out.
- Response caches and vision images have bounded resource budgets. See
  [resource limits and performance](docs/performance.md) for defaults, options,
  and the extraction compatibility switch.
- PDF and OCR processing are not sandboxed. OCR, vision, heuristics, and LLM
  output can be incomplete or incorrect.
- Configured LLM endpoints and post-rename hooks can receive document-derived
  content or metadata.
- Logs, caches, exports, rename logs, and backups can contain private
  document-adjacent information.

Read [SECURITY.md](SECURITY.md) before processing untrusted PDFs or using a
non-loopback integration.

## Repository map

| Path | Responsibility |
| --- | --- |
| `src/folionym/settings/` | configuration models and precedence resolution |
| `src/folionym/naming/` | filename composition, heuristics, dates, templates, and model-assisted document analysis |
| `src/folionym/extraction/` | PDF text, metadata, OCR, and extraction strategies |
| `src/folionym/llm/` | LLM protocols, JSON completion, parsing, cache, and HTTP transport |
| `src/folionym/application/` | discovery, proposals, batch and watch runs, reviewed plans, undo, single-file rename, artifacts, and hooks |
| `src/folionym/rename_ops/` | filename safety, backups, and filesystem mutation |
| `src/folionym/infrastructure/` | low-level file, filename-safety, HTTP, logging, error, and resource primitives |
| `src/folionym/interfaces/` | `cli`, `tui`, and `web` adapters plus the shared `ui_settings` |
| `frontend/` | React 19, TypeScript, and Vite browser source |
| `src/folionym/web_dist/` | generated browser assets included in the wheel |
| `tests/` | `contracts/` (public surface), `workflows/` (end to end), one directory per package, and `tooling/` (repository scripts) |
| `scripts/` | architecture, hygiene, and distribution checks |

The installed commands are `folionym`, `folionym-tui`, `folionym-undo`, and
`folionym-web`. Stable Python import facades are `folionym.config`,
`folionym.filename`, `folionym.heuristics`, `folionym.renamer`, and
`folionym.rename_ops`.

## Development and verification

Run commands from the repository root:

```bash
make format
make lint
make typecheck
make test
make frontend-check
make architecture-check
make release-check
```

`make format` modifies Python files. `make frontend-check` type-checks and
builds the frontend into `src/folionym/web_dist/`. `make release-check` adds
lock validation, repository hygiene, packaging, and an isolated installed-wheel
check to all other gates.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the change workflow,
[DESIGN.md](DESIGN.md) for architecture, and [RELEASING.md](RELEASING.md) for the
manual prerelease procedure.

## Troubleshooting

- Run `folionym --doctor` to inspect optional dependencies, data files, and LLM
  connectivity.
- Add `--no-llm` when the configured endpoint is unavailable.
- Install `.[pdf]`, `.[ocr]`, `.[tui]`, or `.[web]` when the corresponding
  optional feature is unavailable.
- A rename log can undo only safe same-directory moves whose target still
  exists and whose original path is free. Every entry must lie under the rename
  log's directory (its trust root); relative entries resolve against the current
  directory.
- If a source checkout lacks current packaged browser assets, run
  `make frontend-check` after installing frontend dependencies.

## Documentation

- [Product scope](PRODUCT.md)
- [Architecture](DESIGN.md)
- [Browser interface and static demo](docs/frontend.md)
- [Terminal interface](docs/tui.md)
- [Resource limits and performance](docs/performance.md)
- [Security policy](SECURITY.md)
- [Contribution guide](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)
- [Release process](RELEASING.md)
- [Support](SUPPORT.md)
- [Code of conduct](CODE_OF_CONDUCT.md)
- [All documentation](docs/README.md)

## License

Folionym is licensed under the [MIT License](LICENSE).
