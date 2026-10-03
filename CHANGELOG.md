# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Target prerelease: `0.4.0a1`. These entries stay unreleased until the exact
candidate commit is tagged and published as a GitHub prerelease.

### Added

- A README screenshot tour and a matching `tour.html` page in the static demo,
  generated from the deterministic demo build by
  `frontend/tests/capture-screenshots.mjs`.
- Bounded model-session concurrency, response-cache limits, vision image
  budgets, and an explicit full-text extraction compatibility option.
- Dependency-free frontend unit and real-browser workflow tests, plus rendered
  Textual workflow checks.
- Linux full-gate CI plus targeted macOS and Windows smoke coverage on exact
  CPython 3.14.6.
- A deterministic static browser demo build and GitHub Pages workflow that use
  simulated files and never call the local backend.
- Alpha release notes, structured GitHub release-note categories, and a
  maintainer prerelease checklist.
- Alpha package metadata and repository checks for public documentation,
  workflows, and built distributions.
- Architecture guidance and a decision record for the modular-monolith package
  boundaries and shared reviewed-plan contract.

### Changed

- Redesigned the browser interface, static demo, and screenshot tour as a
  numbered rename register (see `DESIGN_BRIEF.md`). Proposed names now stack
  under current names and wrap instead of truncating; review and failure
  reasons appear beside their rows; Source shows an example filename taken
  apart into its fields; the Apply report lists the real status of every file
  and colours only failures as errors. The interface uses Newsreader, Atkinson
  Hyperlegible Next, and Atkinson Hyperlegible Mono instead of IBM Plex. The
  date-order setting is now described as how ambiguous dates are read, not as
  the output date format.
- Rewrote the README and user documentation for a general GitHub audience while
  preserving documented behavior, limits, and contracts.
- Generalized the ignore rules for common Node, editor, OS, and credential
  artifacts.
- Stop PDF text extraction at its token budget and bypass LLM cache hashing for
  heuristic-only naming.
- Bound browser run history and thumbnail memory, load selected evidence lazily,
  and paginate large review and report ledgers.
- Prune directory traversal at the depth limit and defer child-folder counts.
- Audit frozen Python dependencies with all extras and the frontend lockfile.
- Rebranded the product, distribution, Python package, command-line tools,
  environment variables, local state paths, documentation, and release assets as
  Folionym.
- Raised the supported interpreter floor to Python 3.14 and release verification
  to exact CPython 3.14.6 using the standard GIL build.
- Made PyYAML a core runtime dependency for documented YAML configuration.
- Decomposed the CLI, filename, heuristic, LLM, renamer, text, and TUI runtime
  modules around canonical request/configuration objects and module-owned APIs.
- Grouped the implementation into settings, naming, extraction, LLM,
  application, rename, infrastructure, and interface packages while retaining
  the documented public facades.
- Made directory TUI Preview retain an immutable reviewed plan. Its Apply now
  uses exact included ready targets without recomputation; material edits
  invalidate the plan, and an incomplete Preview cannot apply. The confirmed
  single-file TUI path remains immediate and unique-available.
- Added the architecture check to the local release gate.
- Redrew internal module boundaries by responsibility and made the architecture
  check an allowlist ([ADR 0003](docs/decisions/0003-responsibility-based-module-boundaries.md)).
  Logger names now follow modules, which matters with `FOLIONYM_STRUCTURED_LOGS`:
  for example `folionym.heuristics` is now `folionym.naming.scoring`, hooks log
  under `folionym.application.hooks`, and PDF metadata writes under
  `folionym.extraction.writer`. Internal modules moved
  (`folionym.llm.service`, `prompts`, and `simple` are now
  `folionym.naming.analysis`, `prompts`, and `simple_filename`;
  `folionym.rename_ops.naming` is `rename_ops.options`; filename primitives live
  in `infrastructure.filenames`). The public facades are unchanged.
- Restricted post-rename hooks to HTTPS and literal-loopback HTTP endpoints, and
  redacted schema-validation logs so document-derived values are not exposed.
- Restricted LLM endpoints to structurally valid HTTP(S) URLs while keeping the
  documented warning for remote plain HTTP and optional HTTPS enforcement.
- Made CI hygiene and secret scanning unconditional for applicable pushes and
  pull requests.
- Added Ruff complexity guards (`C901`, `PLR0911`, `PLR0912`, `PLR0913`, and
  `PLR0915`) and aligned mypy with Python 3.14.

### Fixed

- The browser folder picker counted symbolic-link PDFs that Preview skips; counts
  now use the same discovery policy as a depth-one Preview.
- Recover browser progress after transient failures with retries and a manual
  reconnect action, and preserve selection across ledger pages and filters.
- Include the architecture checker in source distributions and verify its
  presence.
- Removed duplicate wheel package-data inclusion and added installed-artifact
  verification for the wheel, source distribution, and all four entry points.
- Centralized tracked-path hygiene policy and added regression checks for
  private, credential, document, cache, and local automation paths.
- Switched response-cache identity to full-file hashing with change detection.
- Moved TUI work to managed Textual workers with cancellation-aware shutdown.
- Disabled redirects for LLM and diagnostic POST requests, and redacted endpoint
  and request details from LLM failure logs.
- Corrected the Textual worker-message types used by the strict mypy gate.
- Restored saving of TUI settings when a valid directory Preview starts.
- Made `folionym-web` print the install hint instead of crashing when the `web`
  extra is missing, and removed the import-time application instance.
- Preserved a cancel requested before a reviewed apply worker starts.
- Counted a completed TUI single-file rename in the run summary; it previously
  reported no renamed files.
- Stopped the TUI from writing `error.log` into the working directory; it now
  uses the same default log path as the CLI.
- Applied the documented configuration precedence (explicit CLI option >
  `FOLIONYM_*` environment > `--config` file > preset > built-in default) in
  `build_config`, which every entry point uses: environment values now beat
  config-file values (including `FOLIONYM_MAX_TOKENS`), an explicit CLI
  option equal to its parser default (such as `--workers 1`) beats the file,
  `FOLIONYM_REQUIRE_HTTPS` is enforced during validation, and preset values
  such as `--preset batch` workers rank below file values instead of being
  masked by parser defaults. Presets no longer override explicit CLI options
  (for example `--preset accurate --no-llm` now disables the LLM); the browser
  and TUI, which submit every form value, still apply the selected preset's
  mode switches over the form. `--prefer-llm` is
  now the effective CLI default as documented. For library callers, `build_config(..., file_defaults=...)` now
  applies file values to every setting, not only to the LLM endpoint and
  content limits. Library configurations constructed without `build_config`
  (such as `RenamerConfig()`) still fall back to `FOLIONYM_*` variables at
  call time in `llm.http`, `application.hooks`, and extraction.
- The browser's external-endpoint acknowledgement and the TUI content-boundary
  disclosure now use the endpoint the run will actually contact, resolved
  through `build_config`. Previously an empty endpoint field with a remote
  `FOLIONYM_LLM_URL` skipped the browser acknowledgement and showed a local
  model in the TUI, and a run with the model disabled but vision fallback or
  vision-first enabled was described as keeping content local although it
  sends page images to the endpoint.
- Editing a name in the interactive prompt now strips an uppercase `.PDF`
  suffix as documented, instead of producing `Name.PDF.pdf`.
- Writing PDF title metadata after a rename no longer leaves the file with
  owner-only (`0600`) permissions; the original permission bits are kept.

### Removed

- The obsolete GUI command alias and the former Python compatibility façade.
- Local model-loading, automatic backend selection, embedding-assisted conflict
  resolution, and their retired configuration fields.

## [0.2.0] - 2026-04-19

Development milestone; it was not published as a GitHub release.

### Added

- `--require-https` flag and `FOLIONYM_REQUIRE_HTTPS` environment variable for
  HTTPS enforcement.
- `CategoryCombineParams` frozen dataclass for category merge configuration.
- Path traversal validation in rename operations.
- Thread-safe tiktoken initialization with double-checked locking.
- Test suite growth from 161 to 786 cases, with the coverage threshold raised
  from 50% to 85%.
- LLM backend abstraction: HTTP (llama.cpp / Ollama) and in-process
  (llama-cpp-python).
- Single-call LLM mode for combined summary, keyword, and category extraction.
- Chat API mode with JSON response format support.
- LLM hardware presets: `apple-silicon` (default) and `gpu`.
- Terminal UI (`folionym-tui`) replacing the Tkinter GUI.
- Vision fallback and vision-first modes for scanned PDFs.
- `--preset` flag (`high-confidence-heuristic`, `scanned`).
- `make release-check` target combining hygiene, lint, and tests.
- CI repository hygiene check and security workflow (CodeQL, pip-audit,
  TruffleHog).
- README flowchart and lifecycle state diagram (Mermaid).
- Environment variables table in the README.

### Changed

- Decomposed `renamer.py`: category override lookup into `renamer_lookup.py`,
  CSV/JSON output into `renamer_output.py`, and progress reporting into
  `renamer_progress.py`.
- Decomposed `tui.py`: TUI constants, CSS, and log formatters into
  `tui_assets.py`.
- Narrowed exception handlers from bare `except Exception` to specific types.
- Decomposed `build_config()` into four focused helper functions.
- Decomposed `rename_pdfs_in_directory()` and extracted
  `_write_rename_outputs()`.
- Reduced the `combine_categories()` parameter count from 13 to 5 with a params
  object.
- Strengthened CSV formula-injection prevention per OWASP guidance.
- Raised the coverage threshold from 50% to 85%.
- Brought `tui.py` under mypy strict type checking.
- Switched the default LLM endpoint to Ollama (`http://127.0.0.1:11434`) via
  presets.
- Reorganized the README for clarity and a quicker start.
- Updated CONTRIBUTING with an architecture table.

### Fixed

- Eliminated a TOCTOU race condition in `apply_single_rename()`.
- Documented the mutable default parameter pattern in the rename closure.
- Silent failure paths now log at debug level.
- `combine_categories()` returned the LLM category even when invalid, because
  both branches of the conditional returned the same value.
- Updated `_write_pdf_title_metadata()` tests to match the atomic
  tempfile-based save implementation.
- Fixed Ruff lint violations: import ordering, `contextlib.suppress` usage, and
  line length.

### Removed

- The Tkinter GUI (`gui.py`), replaced by the TUI.
- Ollama-specific code and global thread-local session management.
- `requirements.txt`; use the `pyproject.toml` optional dependency groups.

## [0.1.0] - 2026-03-01

Development milestone; it was not published as a GitHub release.

### Added

- Initial public release baseline for local-first PDF renaming with a CLI and
  GUI.
