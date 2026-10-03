# ADR 0002: Keep the modular-monolith boundaries and share reviewed plans

- Status: Accepted

Note: [ADR 0003](0003-responsibility-based-module-boundaries.md) refines these module boundaries.

## Context

Folionym runs as one local Python application, but it has distinct concerns:
configuration, document extraction, deterministic naming, optional LLM
transport, workflow orchestration, filesystem mutation, and several user
interfaces. A flat module layout made those boundaries unclear and let interfaces
own workflow decisions.

Browser and directory-TUI users both review proposed names before requesting a
rename. Reimplementing that process per interface risked one interface
recomputing a name or resolving a collision differently from another.

## Decision

Keep one modular monolith. `settings`, `naming`, `extraction`, `llm`,
`application`, `rename_ops`, `infrastructure`, and `interfaces` own the
responsibilities described in [DESIGN.md](../../DESIGN.md). Dependencies point
from interfaces and application toward the domain packages and infrastructure,
and infrastructure does not import higher layers. Public top-level facades keep
the documented imports working while internal work stays package-local.

`application.reviewed_plan` owns immutable Preview plans and exact reviewed
Apply. The browser and directory TUI adapt that same contract. A reviewed Apply
rechecks source identity and exact target availability and fails on a conflict
rather than selecting a different name. TUI single-file rename and conventional
CLI batch operation keep using explicit unique-available workflows, and CLI plan
files stay export artifacts rather than reviewed-plan input.

Filesystem safety stays in `rename_ops` under
[ADR 0001](0001-rename-filesystem-boundary.md). This decision does not replace
that mutation boundary; it specifies which callers may request each policy.

## Consequences

Interfaces stay thin and agree on reviewed-plan behavior, and tests can target
application contracts independently of Textual or FastAPI. The cost is that new
behavior must be placed deliberately and cross-package imports need review, but
the alternative would duplicate safety policy across interfaces.
