"""Typed proposal statuses and the ordered, cancellable proposal scheduler."""

from __future__ import annotations

import threading
from pathlib import Path

from folionym.application.models import PreviewStatus, Proposal
from folionym.application.scheduling import (
    ProposalProductionDependencies,
    ProposalProductionRequest,
    produce_proposals_with,
)
from folionym.config import RenamerConfig, build_config


def test_typed_proposal_statuses_preserve_empty_and_error_distinctions(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"

    assert Proposal(source, "invoice", {}).status is PreviewStatus.READY
    assert Proposal(source, None, None).status is PreviewStatus.SKIPPED
    assert Proposal(source, None, None, ValueError("bad PDF")).status is PreviewStatus.FAILED


def test_scheduler_preserves_input_order_and_stops_before_sequential_work(tmp_path: Path) -> None:
    files = [tmp_path / f"{index}.pdf" for index in range(3)]
    config = RenamerConfig()
    completed: list[Path] = []

    def process(path: Path, _config: RenamerConfig, _rules: object, _client: object) -> Proposal:
        completed.append(path)
        return Proposal(path, f"renamed-{path.stem}", {})

    dependencies = ProposalProductionDependencies(
        process_one_file=process,
        recoverable_exceptions=(ValueError,),
    )
    request = ProposalProductionRequest(files, config, None, None, 2, None)

    proposals = produce_proposals_with(request, dependencies)

    assert [proposal.source for proposal in proposals] == files
    assert set(completed) == set(files)

    completed.clear()
    stop_event = threading.Event()
    stop_event.set()
    stopped_config = build_config({"stop_event": stop_event})
    stopped = produce_proposals_with(
        ProposalProductionRequest(files, stopped_config, None, None, 1, None),
        dependencies,
    )
    assert stopped == []
    assert completed == []
