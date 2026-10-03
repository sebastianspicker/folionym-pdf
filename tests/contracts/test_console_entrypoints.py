"""Console entry points and --help stay usable without installed console scripts."""

from __future__ import annotations

import logging
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from folionym.interfaces.cli import main as cli_main
from folionym.interfaces.cli.parser import build_parser
from folionym.interfaces.cli.undo import main as undo_main
from folionym.interfaces.tui import main as tui_main
from folionym.interfaces.web.cli import main as web_main


def test_main_cli_help_and_parser_stay_usable_without_installed_scripts(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli_main(["--help"])
    assert exc_info.value.code == 0
    assert "--validate-config" in capsys.readouterr().out

    parsed = build_parser().parse_args(["--dir", "incoming", "--dry-run", "--no-llm"])
    assert (parsed.dirs, parsed.dry_run, parsed.use_llm) == (["incoming"], True, False)


@pytest.mark.parametrize(
    ("entrypoint", "argv", "expected"),
    [
        (undo_main, ["--help"], "folionym-undo"),
        (web_main, ["--help"], "--no-open"),
    ],
)
def test_argument_parsing_help_for_secondary_console_entrypoints(
    entrypoint: Callable[[list[str] | None], None], argv: list[str], expected: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        entrypoint(argv)
    assert exc_info.value.code == 0
    assert expected in capsys.readouterr().out


def test_tui_console_entrypoint_starts_its_app_without_using_script_installation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: list[bool] = []

    class FakeTui:
        def run(self) -> None:
            started.append(True)

    monkeypatch.setattr("folionym.interfaces.tui.app.FolionymTUI", FakeTui)
    tui_main()
    assert started == [True]


def test_tui_console_entrypoint_does_not_write_error_log_into_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    workdir = tmp_path / "work"
    home.mkdir()
    workdir.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("FOLIONYM_LOG_FILE", raising=False)
    monkeypatch.chdir(workdir)
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level

    class FakeTui:
        def run(self) -> None:
            return None

    monkeypatch.setattr("folionym.interfaces.tui.app.FolionymTUI", FakeTui)
    try:
        tui_main()
    finally:
        for handler in list(root.handlers):
            if handler not in handlers:
                root.removeHandler(handler)
                handler.close()
        root.setLevel(level)
    assert not (workdir / "error.log").exists()
    assert (home / ".local" / "share" / "folionym" / "error.log").exists()


def test_web_launcher_reports_the_missing_extra_without_importing_fastapi() -> None:
    script = (
        "import sys\n"
        "for name in ('fastapi', 'uvicorn', 'starlette'):\n"
        "    sys.modules[name] = None\n"
        "from folionym.interfaces.web.cli import main\n"
        "main(['--no-open'])\n"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=False)
    assert result.returncode == 1
    assert "Install the browser frontend with: pip install 'folionym[web]'" in result.stderr
    assert "ModuleNotFoundError" not in result.stderr


def test_importing_the_renamer_facade_does_not_load_the_cli_main_module() -> None:
    script = (
        "import sys\n"
        "import folionym.renamer\n"
        "assert 'folionym.interfaces.cli.command' not in sys.modules\n"
        "from folionym.interfaces.cli import main\n"
        "assert callable(main) and 'folionym.interfaces.cli.command' in sys.modules\n"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_cli_launcher_stays_callable_when_the_command_module_was_imported_first() -> None:
    import importlib

    importlib.import_module("folionym.interfaces.cli.command")
    from folionym.interfaces.cli import main

    assert callable(main)
