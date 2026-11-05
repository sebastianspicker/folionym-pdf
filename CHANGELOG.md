# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Target prerelease: `0.4.0a1`. These entries stay unreleased until the exact
candidate commit is tagged and published as a GitHub prerelease.

### Added

- A README screenshot tour and a matching `tour.html` page in the static demo,
  generated from the deterministic demo build.
- Bounded model-session concurrency, response-cache limits, vision image
  budgets, and an explicit full-text extraction compatibility option.
- Linux full-gate CI on exact CPython 3.14.6.
- A deterministic static browser demo build and GitHub Pages workflow that use
  simulated files and never call the local backend.
- Alpha release notes, structured GitHub release-note categories, and a
  maintainer prerelease checklist.
- Alpha package metadata and repository checks for public documentation,
  workflows, and built distributions.
- Architecture guidance and a decision record for the modular-monolith package
  boundaries and shared reviewed-plan contract.

### Changed

- `DESIGN.md` explains how each command runs, how one PDF becomes a proposed
  name, the browser's HTTP and event flow, plan item states, and the build and
  release pipeline, each linked to the code that implements it.
- `--plan-file`, `--export-metadata` and `--summary-json` are refused together
  with several `--dir` folders or `--watch`. Each folder, and each watched
  file, is a separate run that rewrote these files, so they used to keep only
  the last run.
- `folionym-undo` exits with status 1 when an entry could not be reverted and
  prints a one-line total of reverted, skipped and failed entries.
- An unrecognised boolean in a config file or `FOLIONYM_*` variable (such as
  `use_llm: flase`) keeps the default instead of counting as true. Values that
  do not parse and unknown `preset` names are now named in a warning.
- General CI runs automatically only for Dependabot-authored pull requests;
  ordinary builds remain available manually. Security scans retain their own
  triggers. Pages deployment requires a manual run on `main`.
- Enable weekly native uv, npm frontend and GitHub Actions dependency updates.

- The default document language is now English (`en`), including the OCR
  language (`eng`). German stays fully supported with `--language de` or
  `language: de` in a config file. The browser and terminal app also default
  to English, list it first, and keep a language you saved earlier.
- `folionym` no longer asks for language, case, project, version or a
  directory just because it runs in a terminal. These questions are asked only
  with `--interactive` (or `--manual`); otherwise the defaults are used and a
  missing directory is an error.
- Heuristic-only naming recognises more English and German documents under
  either `--language` setting: English lease and tenancy agreements,
  employment, loan and purchase agreements, statements of account, notices of
  assessment, utility bills, notices to vacate, reference letters, move-in
  inspection reports, house rules, packing lists, discharge summaries and
  "certificate of birth/marriage/death" titles, and German compounds such as
  Einkommensteuererklärung, Einkommensteuerbescheid, Versicherungsschein,
  Darlehensvertrag, Betriebskostenabrechnung, Übergabeprotokoll, Befundbericht,
  Kassenbon and "Kündigung des Mietverhältnisses". Payment reminders that cite
  the invoice they chase are no longer named as invoices, utility statements
  are no longer named as payslips, and move-in inspection reports are no
  longer named as vehicle inspections.
- Re-themed the browser interface and Pages site as "Highlighter": ink on a
  cool off-white, Geist and Geist Mono instead of Newsreader and Atkinson
  Hyperlegible, and one chartreuse marker used only for model output and what
  will be written (the new parts of ticked names, renamed files, the primary
  action). Interface copy is plain and task-first.
- Reworked the browser interface for small screens and the Pages site. The
  demo marker now sits in the masthead (56px on desktop, 80px on phones) and
  links to an About page; Build preview sits inside the source panel so it is
  visible without scrolling; Preview evidence opens as a bottom sheet below
  900px and the status filters no longer clip; the Apply tally lists only
  outcomes that happened. Field labels are sentence case, interface icons come
  from Phosphor, and demo thumbnails are rendered first pages of simulated
  sample documents. The screenshot tour is replaced by a landing page built
  from `frontend/tour.html` at the same `tour.html` address.
- Redesigned the browser interface, static demo, and screenshot tour as a
  numbered rename register. Proposed names now stack
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

### Security

- `folionym-web` now opens a link with a single-use random token and issues its
  session cookie, a separate secret, only to the first request that presents
  it. Before, any local program could ask for the cookie and then use the whole
  browser API. The link is also printed, for `--no-open` and the Vite dev
  server.
- Filenames no longer keep control characters (including C1), lone
  surrogates, line separators or invisible format characters such as the
  right-to-left override, which could make a new name display as a different
  one. Unusual spaces become plain spaces; the zero-width non-joiner and
  joiner used in Persian and Indic words are kept.

### Fixed

- The filename date no longer comes from an 8-digit customer, invoice or order
  number when the text also has a written date such as `12.03.2024`, and
  dates with a two-digit year and two-digit day and month (`15.01.24`) are
  read. Version or section numbers such as `1.2.15` are not taken as dates.
- Vision fallback now runs for image-only PDFs instead of skipping them, and a
  vision answer such as `INVOICE_AMAZON_2023-11-15` yields
  `20231115-invoice` instead of a dated `document` name.
- `--ocr` no longer stops the whole run when OCRmyPDF refuses a PDF (for
  example one that already has a small text layer). Pages that already have
  text are kept, only empty pages are recognised, and OCRmyPDF's own progress
  bars are no longer printed.
- Invoice-number extraction no longer slows down sharply on long runs of
  blanks after a label such as "Rechnungsnummer".
- A model URL ending in `/v1` (for example `http://127.0.0.1:11434/v1`) now
  reaches `/v1/chat/completions` or `/v1/completions` instead of failing with
  404 on every request.
- A malformed `--template` (`{date`, `{0}`, `{date!x}`) is reported once when
  the configuration is built instead of failing every file, and empty template
  fields no longer leave doubled or trailing separators.
- Keywords that differ only in case appear once in a filename.
- Renames on volumes without hard links (exFAT, most SMB shares) now use an
  atomic no-replace rename where the system offers one, and the copy fallback,
  backups and `--write-pdf-metadata` keep extended attributes such as Finder
  tags, plus the creation date on macOS.
- Ctrl+C at an `--interactive` prompt stops the run (exit 130) instead of only
  skipping the current file.
- In the browser, an apply that was stopped after some files now opens its
  report, a double click on Apply sends one request, an apply error is shown
  above the list instead of replacing the page, the privacy label also counts
  vision settings and `FOLIONYM_LLM_URL`, and the progress window no longer
  moves keyboard focus away from "Stop" on every finished file.
- Check Preview paths against resolved filesystem roots, including directory
  aliases, while retaining downstream source-symlink rejection.

- Refresh the locked security fixes for certifi 2026.10.18, Pillow 13.0.0,
  fpdf2 2.8.8, and the frontend development server Vite 8.1.6.

- The README quick start and `folionym --help` now state the default document
  language and that it also selects the OCR language.
- Re-running a conventional CLI apply, a TUI single-file rename, or watch mode
  (including after a restart) on files that already carry their proposed name
  no longer renames them again with a `_1` suffix, and no longer writes another
  backup or rename-log line for them. They are reported as already named and
  counted as skipped.
- The fallback name for a document whose category, summary and keywords are
  all unknown is now `<date>-document` (or the configured segment) without the
  time of day, so a dry run, the following apply and later runs propose the
  same name as long as the document date does not change (a document with no
  date in its text or metadata gets today's date). Several such files from one
  date receive the usual `_1`, `_2` suffixes on apply; a dry run still shows
  the unsuffixed name for each of them.
- A `--plan-file` run without `--dry-run` no longer logs "Renamed" for each
  file, and the summary of a dry run or plan-file run says "would rename"
  instead of "renamed". The `--summary-json` file of a plan-file run now
  reports `"dry_run": true`, since nothing on disk changed.
- With the `tokens` extra installed and no cached tiktoken encoding, an offline
  or proxied machine no longer fails every PDF: the failed encoding download is
  logged once and token counts fall back to the length estimate. The download
  is now documented in the README and `SECURITY.md`.
- Kept browser consent for external model endpoints process-local, bound retries
  to the exact resolved endpoint, and stopped restoring consent from shared UI
  settings.
- Bound recursive discovery, native PDF reads, reviewed Apply, backups, and copy
  fallbacks to verified file identities so concurrent path substitution cannot
  redirect processing or apply an approved rename to different bytes.
- Retained the private PDF-metadata temporary descriptor through serialization,
  mode changes, validation, and publication instead of trusting a mutable temp
  pathname.
- Escaped terminal controls in CLI and plain-log output and rendered reviewed
  TUI filenames as literal Rich text, preventing crafted names from concealing
  or restyling authorization displays.
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

- The unused browser API route that downloaded a preview's rename log,
  metadata export or summary file.
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
