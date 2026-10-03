"""Exercise real Textual widgets and event delivery with private synthetic settings."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from textual.widgets import DataTable, Input

from folionym.application.models import PreviewItem, PreviewPlan, PreviewStatus
from folionym.interfaces.tui import app as tui
from folionym.interfaces.tui.worker_messages import _PreviewFinished
from folionym.settings import RenamerConfig


@pytest.mark.parametrize("size", [(80, 24), (140, 45)])
def test_rendered_preview_and_material_edit_invalidation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, size: tuple[int, int]
) -> None:
    monkeypatch.setattr(tui, "_load_settings", lambda: {"directory": str(tmp_path), "use_llm": False})
    monkeypatch.setattr(tui, "_save_settings", lambda _settings: None)
    item = PreviewItem("one", tmp_path / "source.pdf", "invoice", {}, PreviewStatus.READY, True, None)
    plan = PreviewPlan("plan", tmp_path, "directory", RenamerConfig(), (item,), datetime.now(UTC))

    async def exercise() -> None:
        app = tui.FolionymTUI()
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            app.post_message(_PreviewFinished(plan, complete=True))
            await pilot.pause()
            assert app.query_one("#preview-table", DataTable).row_count == 1
            assert app._reviewed_plan.require_apply() == (plan, ("one",))
            app.query_one("#directory", Input).value = str(tmp_path / "changed")
            await pilot.pause()
            assert app._reviewed_plan.plan is None
            assert app.query_one("#preview-table", DataTable).row_count == 0

    asyncio.run(exercise())


def test_valid_directory_preview_start_saves_ui_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    saved: list[dict[str, object]] = []
    monkeypatch.setattr(tui, "_load_settings", lambda: {"directory": str(tmp_path), "use_llm": False})
    monkeypatch.setattr(tui, "_save_settings", saved.append)
    monkeypatch.setattr(tui.FolionymTUI, "preview_directory_worker", lambda *_args: None)

    async def exercise() -> None:
        app = tui.FolionymTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.query_one("#directory", Input).value = str(tmp_path / "missing")
            app.start_preview()
            await pilot.pause()
            assert saved == []
            app.query_one("#directory", Input).value = str(tmp_path)
            app.start_preview()
            await pilot.pause()

    asyncio.run(exercise())
    assert len(saved) == 1
    assert saved[0]["directory"] == str(tmp_path)


def test_review_table_treats_filename_markup_and_controls_as_literal_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tui, "_load_settings", lambda: {"directory": str(tmp_path), "use_llm": False})
    monkeypatch.setattr(tui, "_save_settings", lambda _settings: None)
    item = PreviewItem(
        "one",
        tmp_path / "[conceal]bad\x1b[2J.pdf",
        "[red]proposal",
        {},
        PreviewStatus.READY,
        True,
        None,
    )
    plan = PreviewPlan("plan", tmp_path, "directory", RenamerConfig(), (item,), datetime.now(UTC))

    async def exercise() -> None:
        app = tui.FolionymTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.post_message(_PreviewFinished(plan, complete=True))
            await pilot.pause()
            row = app.query_one("#preview-table", DataTable).get_row_at(0)
            assert row[1].plain == "[conceal]bad\\x1b[2J.pdf"
            assert row[2].plain == "[red]proposal.pdf"
            assert "\x1b" not in row[1].plain

    asyncio.run(exercise())


def test_single_file_rename_counts_its_structured_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_pdf: Callable[..., Path], invoice_text: str
) -> None:
    """A completed single-file rename is counted as renamed; counts do not depend on log text."""
    from folionym.config import build_config
    from folionym.interfaces.tui.operations import process_single_file
    from folionym.interfaces.tui.worker_messages import _RunFinished

    source = make_pdf(tmp_path / "source.pdf", invoice_text)
    monkeypatch.setenv("HOME", str(tmp_path))
    result = process_single_file(source, build_config({"use_llm": False, "use_cache": False}))
    assert (result.ok, result.outcome) == (True, "renamed")
    assert not source.exists()

    monkeypatch.setattr(tui, "_load_settings", lambda: {"directory": str(tmp_path), "use_llm": False})
    monkeypatch.setattr(tui, "_save_settings", lambda _settings: None)

    async def exercise() -> None:
        app = tui.FolionymTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.post_message(_RunFinished(result.ok, result.message, result.outcome))
            await pilot.pause()
            assert "1" in str(app.query_one("#metric-suggestions").render())

    asyncio.run(exercise())
