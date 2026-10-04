from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "check_architecture", Path(__file__).parents[2] / "scripts" / "check_architecture.py"
)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
check_architecture = _MODULE.check_architecture

REAL_SOURCE_ROOT = Path(__file__).parents[2] / "src" / "folionym"


def _write(package_root: Path, relative_path: str, contents: str = "") -> None:
    path = package_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def test_check_architecture_accepts_the_real_source_tree() -> None:
    assert (REAL_SOURCE_ROOT / "__init__.py").is_file()
    assert check_architecture(REAL_SOURCE_ROOT) == []


def test_check_architecture_rejects_edges_missing_from_the_allowlist(tmp_path: Path) -> None:
    package_root = tmp_path / "folionym"
    _write(package_root, "naming/service.py", "from folionym.application import Proposal\n")

    assert check_architecture(package_root) == [
        "src/folionym/naming/service.py:1: architecture violation: "
        "naming cannot import application (found 'folionym.application')"
    ]


def test_check_architecture_resolves_relative_imports(tmp_path: Path) -> None:
    package_root = tmp_path / "folionym"
    _write(package_root, "infrastructure/files.py", "from ..settings import RenamerConfig\n")
    _write(package_root, "llm/deep/client.py", "from ...application import Proposal\n")

    assert check_architecture(package_root) == [
        (
            "src/folionym/infrastructure/files.py:1: architecture violation: "
            "infrastructure cannot import settings (found 'folionym.settings')"
        ),
        (
            "src/folionym/llm/deep/client.py:1: architecture violation: "
            "llm cannot import application (found 'folionym.application')"
        ),
    ]


def test_check_architecture_allows_listed_edges_and_same_owner_imports(tmp_path: Path) -> None:
    package_root = tmp_path / "folionym"
    _write(package_root, "naming/service.py", "from ..llm import http\nfrom . import helpers\n")
    _write(package_root, "llm/client.py", "from ._private import _helper\n")

    assert check_architecture(package_root) == []


def test_check_architecture_rejects_sibling_interface_adapters(tmp_path: Path) -> None:
    package_root = tmp_path / "folionym"
    _write(package_root, "interfaces/web/app.py", "from ..tui import app\n")
    _write(package_root, "interfaces/tui/app.py", "from ..ui_settings import UiSettingsSnapshot\n")

    assert check_architecture(package_root) == [
        "src/folionym/interfaces/web/app.py:1: architecture violation: "
        "interfaces.web cannot import interfaces.tui (found 'folionym.interfaces.tui')"
    ]


def test_check_architecture_rejects_adapter_imports_of_rename_ops(tmp_path: Path) -> None:
    package_root = tmp_path / "folionym"
    _write(package_root, "interfaces/cli/main.py", "from ...rename_ops import apply_plan\n")

    assert check_architecture(package_root) == [
        "src/folionym/interfaces/cli/main.py:1: architecture violation: "
        "interfaces.cli cannot import rename_ops (found 'folionym.rename_ops')"
    ]


def test_check_architecture_rejects_internal_imports_through_public_facades(tmp_path: Path) -> None:
    package_root = tmp_path / "folionym"
    _write(package_root, "application/proposals.py", "from ..filename import generate_filename\n")

    assert check_architecture(package_root) == [
        "src/folionym/application/proposals.py:1: architecture violation: "
        "application cannot import outward public facade filename (found 'folionym.filename')"
    ]


def test_check_architecture_rejects_cross_owner_private_imports(tmp_path: Path) -> None:
    package_root = tmp_path / "folionym"
    _write(package_root, "interfaces/cli/main.py", "from ...llm.http import _chat_url\n")

    assert check_architecture(package_root) == [
        "src/folionym/interfaces/cli/main.py:1: architecture violation: "
        "interfaces.cli cannot import private name _chat_url from llm (found 'folionym.llm.http._chat_url')"
    ]


def test_check_architecture_rejects_forbidden_external_libraries(tmp_path: Path) -> None:
    package_root = tmp_path / "folionym"
    _write(package_root, "naming/service.py", "import requests\n")
    _write(package_root, "application/models.py", "from fastapi import FastAPI\n")
    _write(package_root, "llm/parser.py", "import requests\n")
    _write(package_root, "llm/http.py", "import requests\n")
    _write(package_root, "extraction/pdf.py", "import fitz\n")
    _write(package_root, "interfaces/cli/terminal.py", "from textual.app import App\n")

    assert check_architecture(package_root) == [
        (
            "src/folionym/application/models.py:1: architecture violation: "
            "application cannot import fastapi (found 'fastapi')"
        ),
        (
            "src/folionym/interfaces/cli/terminal.py:1: architecture violation: "
            "interfaces.cli cannot import textual (found 'textual.app')"
        ),
        "src/folionym/llm/parser.py:1: architecture violation: llm cannot import requests (found 'requests')",
        "src/folionym/naming/service.py:1: architecture violation: naming cannot import requests (found 'requests')",
    ]


def test_check_architecture_rejects_root_layout_debris(tmp_path: Path) -> None:
    package_root = tmp_path / "folionym"
    _write(package_root, "temporary.py")

    assert check_architecture(package_root) == [
        "src/folionym/temporary.py:1: architecture violation: "
        "production package root only permits public facades and metadata"
    ]


def test_check_architecture_rejects_modules_with_an_unknown_owner(tmp_path: Path) -> None:
    package_root = tmp_path / "folionym"
    _write(package_root, "newpkg/service.py")
    _write(package_root, "interfaces/extra.py")
    _write(package_root, "interfaces/gui/window.py")

    assert check_architecture(package_root) == [
        (
            "src/folionym/interfaces/extra.py:1: architecture violation: "
            "unknown owner for module folionym.interfaces.extra — add it to ALLOWED_DEPENDENCIES"
        ),
        (
            "src/folionym/interfaces/gui/window.py:1: architecture violation: "
            "unknown owner for module folionym.interfaces.gui.window — add it to ALLOWED_DEPENDENCIES"
        ),
        (
            "src/folionym/newpkg/service.py:1: architecture violation: "
            "unknown owner for module folionym.newpkg.service — add it to ALLOWED_DEPENDENCIES"
        ),
    ]


def test_check_architecture_rejects_imports_of_an_unknown_owner(tmp_path: Path) -> None:
    package_root = tmp_path / "folionym"
    _write(package_root, "naming/service.py", "from folionym.newpkg import thing\n")

    assert check_architecture(package_root) == [
        "src/folionym/naming/service.py:1: architecture violation: "
        "naming cannot import unknown owner (found 'folionym.newpkg') — add it to ALLOWED_DEPENDENCIES"
    ]


def test_check_architecture_restricts_pydantic_and_yaml(tmp_path: Path) -> None:
    package_root = tmp_path / "folionym"
    _write(package_root, "interfaces/web/schema.py", "from pydantic import BaseModel\n")
    _write(package_root, "interfaces/cli/config.py", "import yaml\n")
    _write(package_root, "application/models.py", "from pydantic import BaseModel\n")
    _write(package_root, "interfaces/cli/other.py", "import yaml\n")

    assert check_architecture(package_root) == [
        (
            "src/folionym/application/models.py:1: architecture violation: "
            "application cannot import pydantic (found 'pydantic')"
        ),
        (
            "src/folionym/interfaces/cli/other.py:1: architecture violation: "
            "interfaces.cli cannot import yaml (found 'yaml')"
        ),
    ]


def test_every_allowed_dependency_is_used_by_the_real_source_tree() -> None:
    """Keep the allowlist minimal: an edge nobody imports any more must be removed from it."""
    import ast

    used: dict[str, set[str]] = {owner: set() for owner in _MODULE.ALLOWED_DEPENDENCIES}
    for path in REAL_SOURCE_ROOT.rglob("*.py"):
        owner = _MODULE._owner_for_path(path, REAL_SOURCE_ROOT)
        if owner is None:
            continue
        package = _MODULE._package_name(path, REAL_SOURCE_ROOT)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for target in _MODULE._import_targets(node, package):
                    target_owner = _MODULE._owner_for_module(target)
                    if target_owner is not None and target_owner != owner:
                        used[owner].add(target_owner)

    unused = {
        owner: sorted(set(allowed) - used[owner])
        for owner, allowed in _MODULE.ALLOWED_DEPENDENCIES.items()
        if set(allowed) - used[owner]
    }
    assert unused == {}
