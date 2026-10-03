# ADR 0001: Preserve the rename filesystem boundary

- Status: Accepted
- Date: 2026-08-09

## Context

Rename operations combine filename policy, collision handling, backups,
cross-filesystem fallbacks, dry runs, plan output, and completion callbacks.
Keeping all of that in one module made the mutation boundary hard to review, even
though callers already imported from `folionym.rename_ops`.

## Decision

`folionym.rename_ops` remains the stable public facade. Its implementation is
split into options, backup, filesystem, and execution modules. External callers
use the names exported by `rename_ops.__all__`. Inside Folionym only the
application layer calls `rename_ops` (interfaces may not, and the architecture
check enforces it) and it may use the modules directly; for example
`application.undo` uses `rename_ops.execution.apply_exact_rename`.
Filename-safety primitives live in `infrastructure.filenames` and are
re-exported by `rename_ops`.

Every implementation change must preserve these filesystem invariants:

- an existing target is never overwritten; collisions select a unique suffix
  unless an exact reviewed target was required;
- dry-run and plan output choose the same collision target as apply;
- backups are created once before mutation, use unique names, and are private
  where the platform supports POSIX permissions;
- cross-filesystem fallback reserves and validates the destination before
  unlinking the source, and cleans incomplete targets after failure;
- completion callbacks cannot turn an already completed rename into a failed
  filesystem operation.

## Consequences

New rename behavior belongs in the owning implementation module without bypassing
the facade. Changing exports or invariants requires an explicit contract update
and focused tests. The retained direct contracts are covered by
`tests/rename_ops/`, `tests/interfaces/test_cli_undo.py`, and
`tests/application/test_post_rename_hook.py`.
