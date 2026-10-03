"""Real synthetic PDFs cross extraction, naming, reviewed plans, and safe Apply."""

from collections.abc import Callable
from pathlib import Path

import pytest

from folionym.application.models import ApplyStatus, PreviewStatus
from folionym.application.reviewed_plan import apply_reviewed_plan, create_preview_plan
from folionym.llm.cache import ResponseCache
from folionym.settings.resolution import build_config


def test_small_pdf_names_match_full_mode_and_apply_keeps_exact_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_pdf: Callable[..., Path], invoice_text: str
) -> None:
    source = make_pdf(tmp_path / "source.pdf", invoice_text)
    original = source.read_bytes()
    monkeypatch.setattr(ResponseCache, "build_file_key", lambda _path: pytest.fail("heuristics must not hash for LLM"))
    budgeted = create_preview_plan(source, build_config({"use_llm": False}))
    full = create_preview_plan(source, build_config({"use_llm": False, "full_text_extraction": True}))
    assert budgeted.items[0].proposed_name == full.items[0].proposed_name
    assert budgeted.items[0].metadata == full.items[0].metadata
    assert budgeted.items[0].status in {PreviewStatus.READY, PreviewStatus.REVIEW}
    report = apply_reviewed_plan(budgeted, [budgeted.items[0].id])
    assert report.items[0].status is ApplyStatus.RENAMED
    target = tmp_path / str(budgeted.items[0].proposed_name)
    assert target.read_bytes() == original and not source.exists()
