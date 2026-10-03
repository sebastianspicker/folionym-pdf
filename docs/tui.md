# Terminal interface

Folionym ships a Textual interface for local, supervised PDF naming.

```bash
python -m pip install -e '.[tui,pdf]'
folionym-tui
```

## Workflow

The tabs are **Setup**, **Fine-tune**, and **Review and rename**. The directory
workflow is a reviewed-plan workflow:

1. **Preview folder** creates and displays an immutable plan of proposed names.
2. A completed Preview keeps its exact proposed names; only included `READY`
   rows are candidates for Apply.
3. **Apply to folder** confirms and applies those exact retained targets. It
   never recomputes proposals or replaces a collision with a suffix.

The TUI invalidates the retained directory plan after a material source or
setting edit. A cancelled or incomplete Preview stays visible but cannot be
applied. Applying a plan consumes it, so a second Apply needs a fresh Preview.
The Apply confirmation puts Cancel first.

**Rename one PDF** is intentionally different: after confirmation it generates
and immediately applies a unique-available name. Starting that action invalidates
any directory plan. Its run summary counts the file as renamed, skipped (no
extractable content), or failed.

## Controls

| Shortcut | Action |
| --- | --- |
| `Ctrl+P` | Preview folder |
| `Ctrl+A` | confirm exact reviewed folder Apply |
| `Ctrl+C` | request cancellation after the current file |
| `Ctrl+Q` | request cancellation, then quit after the active file |

Starting a valid directory Preview saves the current form values in
`~/.folionym_ui.json`. An existing `~/.folionym_tui.json` is migrated without
deleting the old file. On POSIX, writes use owner-only permissions where
supported.

## Status and limits

The Review tab renders source-to-target rows from the retained typed plan and
keeps a bounded activity log. Status words include `IDLE`, `RUN`, `DONE`,
`FAIL`, and `STOP`, so state does not depend on color alone. Use a
color-capable terminal of at least 80 by 24 cells; terminal and screen-reader
behavior still depends on the platform.

Endpoint URLs must be valid HTTP(S) without embedded credentials. LLM requests
do not follow redirects, and remote plain HTTP warns unless HTTPS is required.
LLM endpoints and post-rename hooks can receive document-derived content. The
TUI does not load models in-process. There is no hard input byte limit, default
extraction is unlimited, workers have no hard maximum, and OCR has no
application-level timeout. Keep backups of important documents and read
[SECURITY.md](../SECURITY.md).
