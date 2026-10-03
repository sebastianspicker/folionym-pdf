"""Enforce Folionym's package dependency graph as an allowlist.

Every cross-owner import inside ``folionym`` must appear in ``ALLOWED_DEPENDENCIES``;
adding an edge is a deliberate, reviewed change to this file.
"""

from __future__ import annotations

import argparse
import ast
from collections.abc import Iterable
from pathlib import Path

PROJECT_PACKAGE = "folionym"

# Owner -> owners it may import (imports within one owner are always allowed).
ALLOWED_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    # Low-level file, HTTP, logging, error and resource primitives; depends on nothing.
    "infrastructure": (),
    # RenamerConfig and configuration resolution.
    "settings": ("infrastructure",),
    # Model access: protocols, parsing, caching and HTTP transport.
    "llm": ("settings", "infrastructure"),
    # Filename safety, backups, collision policy and rename filesystem mutation.
    "rename_ops": ("infrastructure",),
    # PDF text, OCR, metadata, page rendering and the vision prompt.
    "extraction": ("llm", "settings", "infrastructure"),
    # Filename proposals: heuristics, dates, templates and model-assisted document analysis.
    "naming": ("llm", "settings", "infrastructure"),
    # Use cases: discovery, proposals, batch/watch runs, reviewed plans, undo, artifacts and hooks.
    "application": ("settings", "extraction", "naming", "llm", "rename_ops", "infrastructure"),
    # Interface-neutral settings snapshot shared by the TUI and web adapters.
    "interfaces.ui_settings": ("settings", "infrastructure"),
    # Command-line adapter; filesystem mutation goes through application, never rename_ops.
    "interfaces.cli": ("application", "settings", "extraction", "naming", "llm", "infrastructure"),
    # Textual adapter; may share ui_settings but never imports cli or web.
    "interfaces.tui": ("application", "settings", "infrastructure", "interfaces.ui_settings"),
    # Loopback web adapter; may share ui_settings but never imports cli or tui.
    "interfaces.web": ("application", "extraction", "interfaces.ui_settings"),
    # Package metadata only.
    "__init__": (),
    # Public facade over settings.
    "config": ("settings",),
    # Public facade over naming and llm filename helpers.
    "filename": ("naming", "llm"),
    # Public facade over naming heuristics.
    "heuristics": ("naming",),
    # Public facade and composition root using the CLI terminal adapter.
    "renamer": ("application", "settings", "naming", "llm", "interfaces.cli"),
}

ALLOWED_ROOT_MODULES = {"__init__.py", "config.py", "filename.py", "heuristics.py", "renamer.py"}
PUBLIC_FACADE_MODULES = {"config", "filename", "heuristics", "renamer"}
INTERFACE_ADAPTERS = {"cli", "tui", "web", "ui_settings"}

# Third-party libraries that are only permitted where listed below.
RESTRICTED_EXTERNALS = {
    "fastapi",
    "starlette",
    "uvicorn",
    "textual",
    "rich",
    "requests",
    "tiktoken",
    "fitz",
    "ocrmypdf",
    "pydantic",
    "yaml",
}
# Owner or src-relative file -> restricted libraries it may import (union of both keys applies).
ALLOWED_EXTERNALS: dict[str, frozenset[str]] = {
    # PDF engines.
    "extraction": frozenset({"fitz", "ocrmypdf"}),
    # HTTP transport for model requests.
    "llm/http.py": frozenset({"requests"}),
    # HTTP primitives.
    "infrastructure/http.py": frozenset({"requests"}),
    # Recoverable exception groups include requests exceptions.
    "infrastructure/errors.py": frozenset({"requests"}),
    # Token counting.
    "infrastructure/tokens.py": frozenset({"tiktoken"}),
    # Terminal rendering.
    "interfaces.cli": frozenset({"rich"}),
    # Textual user interface.
    "interfaces.tui": frozenset({"textual", "rich"}),
    # Loopback web server.
    "interfaces.web": frozenset({"fastapi", "starlette", "uvicorn", "pydantic"}),
    # Optional YAML configuration files.
    "interfaces/cli/config.py": frozenset({"yaml"}),
}


def _matches_prefix(module: str, prefix: str) -> bool:
    """Return whether *module* is exactly *prefix* or one of its children."""
    return module == prefix or module.startswith(f"{prefix}.")


def _module_name(path: Path, source_root: Path) -> str:
    relative = path.relative_to(source_root).with_suffix("")
    parts = [PROJECT_PACKAGE, *relative.parts]
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _package_name(path: Path, source_root: Path) -> str:
    module = _module_name(path, source_root)
    return module if path.name == "__init__.py" else module.rpartition(".")[0]


def _import_base(node: ast.Import | ast.ImportFrom, package: str) -> str | None:
    """Return the absolute module an ``ImportFrom`` reads from, resolving relative levels."""
    if isinstance(node, ast.Import):
        return None
    if node.level:
        package_parts = package.split(".")
        parent_parts = package_parts[: len(package_parts) - node.level + 1]
        if not parent_parts:
            return None
        base = ".".join(parent_parts)
        return f"{base}.{node.module}" if node.module else base
    return node.module


def _import_targets(node: ast.Import | ast.ImportFrom, package: str) -> Iterable[str]:
    if isinstance(node, ast.Import):
        yield from (alias.name for alias in node.names)
        return
    base = _import_base(node, package)
    if base is None:
        return
    # `from ..interfaces import cli` names a submodule; the bare package is not a dependency.
    if base != f"{PROJECT_PACKAGE}.interfaces":
        yield base
    yield from (f"{base}.{alias.name}" for alias in node.names)


def _owner_of_parts(parts: tuple[str, ...]) -> str | None:
    """Return the owner for path/module parts relative to the package root, or None if unknown."""
    if not parts:
        return None
    first = parts[0]
    if len(parts) == 1:
        first = first.removesuffix(".py")
        # The bare interfaces package re-exports ui_settings, so it shares that owner.
        if first == "interfaces":
            return "interfaces.ui_settings"
        return first if first in ALLOWED_DEPENDENCIES and "." not in first else None
    if first == "interfaces":
        second = parts[1].removesuffix(".py")
        if second == "__init__":
            return "interfaces.ui_settings"
        return f"interfaces.{second}" if second in INTERFACE_ADAPTERS else None
    return first if first in ALLOWED_DEPENDENCIES else None


def _owner_for_path(path: Path, source_root: Path) -> str | None:
    return _owner_of_parts(path.relative_to(source_root).parts)


def _owner_for_module(module: str) -> str | None:
    if not _matches_prefix(module, PROJECT_PACKAGE):
        return None
    return _owner_of_parts(tuple(module.split(".")[1:]))


def _format_path(path: Path, source_root: Path) -> str:
    return str(Path("src") / source_root.name / path.relative_to(source_root))


def _external_import_diagnostic(prefix: str, relative: str, owner: str, target: str) -> str | None:
    """Return a violation when *target* is a restricted third-party library the module may not use."""
    library = target.partition(".")[0]
    allowed = ALLOWED_EXTERNALS.get(owner, frozenset()) | ALLOWED_EXTERNALS.get(relative, frozenset())
    if library in RESTRICTED_EXTERNALS and library not in allowed:
        return f"{prefix} cannot import {library} (found '{target}')"
    return None


def _internal_import_diagnostic(prefix: str, owner: str, target: str) -> str | None:
    """Return a violation when *owner* may not import the project module *target*."""
    if target == PROJECT_PACKAGE:
        return None
    target_owner = _owner_for_module(target)
    if target_owner is None:
        return f"{prefix} cannot import unknown owner (found '{target}') — add it to ALLOWED_DEPENDENCIES"
    if target_owner == owner:
        return None
    for facade in PUBLIC_FACADE_MODULES:
        if _matches_prefix(target, f"{PROJECT_PACKAGE}.{facade}"):
            return f"{prefix} cannot import outward public facade {facade} (found '{target}')"
    if target_owner not in ALLOWED_DEPENDENCIES[owner]:
        return f"{prefix} cannot import {target_owner} (found '{target}')"
    return None


def _check_import(
    *,
    path: Path,
    source_root: Path,
    node: ast.Import | ast.ImportFrom,
    owner: str,
    target: str,
) -> str | None:
    prefix = f"{_format_path(path, source_root)}:{node.lineno}: architecture violation: {owner}"

    if not _matches_prefix(target, PROJECT_PACKAGE):
        return _external_import_diagnostic(prefix, path.relative_to(source_root).as_posix(), owner, target)
    return _internal_import_diagnostic(prefix, owner, target)


def _private_import_diagnostic(
    path: Path, source_root: Path, node: ast.ImportFrom, package: str, owner: str
) -> str | None:
    """Return a violation when *node* imports a single-underscore name from another owner."""
    base = _import_base(node, package)
    if base is None:
        return None
    base_owner = _owner_for_module(base)
    if base_owner is None or base_owner == owner:
        return None
    for alias in node.names:
        if alias.name.startswith("_") and not alias.name.startswith("__"):
            return (
                f"{_format_path(path, source_root)}:{node.lineno}: architecture violation: "
                f"{owner} cannot import private name {alias.name} from {base_owner} (found '{base}.{alias.name}')"
            )
    return None


def _check_file(path: Path, source_root: Path) -> list[str]:
    """Return every violation in one module."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as error:
        line = error.lineno or 1
        return [f"{_format_path(path, source_root)}:{line}: syntax error: {error.msg}"]

    owner = _owner_for_path(path, source_root)
    if owner is None:
        if path.parent == source_root:
            return []  # Reported as root-layout debris by check_architecture.
        return [
            f"{_format_path(path, source_root)}:1: architecture violation: "
            f"unknown owner for module {_module_name(path, source_root)} — add it to ALLOWED_DEPENDENCIES"
        ]
    package = _package_name(path, source_root)
    diagnostics: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        diagnostic = None
        for target in _import_targets(node, package):
            diagnostic = _check_import(path=path, source_root=source_root, node=node, owner=owner, target=target)
            if diagnostic:
                break
        if diagnostic is None and isinstance(node, ast.ImportFrom):
            diagnostic = _private_import_diagnostic(path, source_root, node, package, owner)
        if diagnostic:
            diagnostics.append(diagnostic)
    return diagnostics


def check_architecture(source_root: Path) -> list[str]:
    """Return every package-layout or import-direction violation below *source_root*."""
    source_root = source_root.resolve()
    diagnostics: list[str] = []

    for path in sorted(source_root.glob("*.py")):
        if path.name not in ALLOWED_ROOT_MODULES:
            diagnostics.append(
                f"{_format_path(path, source_root)}:1: architecture violation: "
                "production package root only permits public facades and metadata"
            )

    for path in sorted(source_root.rglob("*.py")):
        diagnostics.extend(_check_file(path, source_root))

    return diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "src" / PROJECT_PACKAGE,
        help="Python package directory to inspect (default: src/folionym)",
    )
    args = parser.parse_args()
    diagnostics = check_architecture(args.source_root)
    if diagnostics:
        print("\n".join(diagnostics))
        return 1
    print(f"Architecture check passed: {args.source_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
