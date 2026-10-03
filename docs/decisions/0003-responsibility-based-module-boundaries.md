# ADR 0003: Draw module boundaries by responsibility and enforce them as an allowlist

- Status: Accepted
- Date: 2026-10-03

## Context

ADR 0002 established the package layout. The packages were right, but the code
inside and between them had drifted from it:

- The application layer performed terminal I/O (prompts, Rich progress, the run
  summary), PDF metadata writes, and raw HTTP; interfaces in turn re-implemented
  application use cases (undo, single-file rename, folder counting, the external
  endpoint decision).
- Modules had been split to satisfy complexity linters rather than ownership, so
  private helpers crossed module and package boundaries, and injection seams
  (`*_with(..., *_fn=)`, `*Dependencies` dataclasses, a facade round-trip) existed
  only so tests could patch internals.
- `naming` was documented as pure while it orchestrated model calls through a
  three-hop chain into `llm`, which itself held document-analysis prompts.
- Configuration had several sources of truth: env var names and defaults were
  repeated across packages, and the CLI merged config-file values in a way that
  broke the documented precedence.
- `scripts/check_architecture.py` was a denylist, so the edges above passed.

## Decision

Keep the modular monolith and its packages. Give each concept one owner:

| Owner | Responsibility |
| --- | --- |
| `infrastructure` | leaf primitives: private files, path and filename safety, URL policy and safe HTTP posts, logging, packaged data, token counting |
| `settings` | configuration models, the precedence table that `build_config` applies (configs built without it fall back to `FOLIONYM_*` variables at call time), env var names and parsing, choice sets and presets |
| `llm` | how to talk to a model: protocol, HTTP transport, response cache, JSON completion and salvage |
| `extraction` | reading and writing PDFs: text, OCR, metadata, page rendering, the vision prompt |
| `naming` | what to ask a model and how to turn answers plus heuristics into a filename |
| `rename_ops` | guarded filesystem mutation (ADR 0001) |
| `application` | use cases: discovery, proposals, batch and watch runs, reviewed plans, undo, single-file rename, artifacts, hooks, the external-endpoint decision |
| `interfaces` | adapters that parse input and present output: CLI (including the terminal prompts and summary), TUI, web |

`scripts/check_architecture.py` enforces this as an allowlist of permitted
edges. It also forbids sibling adapters importing each other, interfaces
importing `rename_ops` (mutation goes through the application), importing
another owner's `_private` names, and framework or transport libraries outside
the adapters that own them.

Compatibility stays at deliberate edges: the five public facades keep their
exports, `folionym.renamer` composes the CLI terminal adapter so its interactive
behaviour is unchanged, and `rename_ops.__all__` is unchanged (it re-exports the
filename primitives that now live in `infrastructure.filenames`). Inside the
project, the application layer may use `rename_ops` modules directly; external
callers use `rename_ops.__all__`.

## Consequences

Each new behaviour has one obvious home, and a new cross-package edge requires
changing the allowlist in review. Tests target public functions, real files, and
HTTP routes; patching private names and injection seams were reduced, not
eliminated. The remaining test seams are deliberate: `extraction_fns` in
`extraction.pipeline`, `ProposalProductionDependencies` in
`application.scheduling`, `reset_encoding_cache` in `infrastructure.tokens`, and
private monkeypatching for filesystem failure injection and TUI/web registry
state. The cost is that adding an edge is
a deliberate edit to the checker, and adapters must express needs through
application functions rather than reaching into domain internals.
