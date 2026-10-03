# Product scope

Folionym is a supervised, local PDF naming application. It extracts document
signals, applies deterministic rules and optional HTTP LLM enrichment, and lets
an operator inspect the proposed names before anything on disk changes.

## Supported workflows

- CLI dry run, batch apply, per-file confirmation, manual single-file, and watch
- Browser Source, Preview, and exact reviewed Apply
- Textual directory Preview and exact reviewed Apply
- Confirmed immediate single-file rename in the TUI
- Constrained undo from a rename log
- Optional OCR and vision for low-text documents
- Proposal-plan, metadata, and run-summary exports
- A deterministic static browser demo with simulated files and outcomes

The [architecture guide](DESIGN.md#principal-flows) is the source of truth for
unique-available and exact-reviewed apply behavior. Interface details live in the
[browser guide](docs/frontend.md) and [terminal guide](docs/tui.md).

## Product constraints

Folionym has no document store, accounts, remote authentication, hosted rename
API, remote browser deployment, or interprocess writer lock. The static demo is
not the local application: it cannot process PDFs or rename files. Optional LLM
endpoints and post-rename hooks are separate network trust boundaries.

## Interface requirements

- Keep source paths, proposed names, statuses, and mutation consequences visible.
- Require Preview before reviewed Apply, and put Cancel first in any destructive
  confirmation.
- Pair color with text labels and preserve keyboard operation.
- Keep advanced extraction, endpoint, and output settings out of the initial
  source selection.
- Describe the browser service as loopback-only, never as remote authentication.
- Label demo data and simulated outcomes so they cannot be mistaken for local
  filesystem operations.
