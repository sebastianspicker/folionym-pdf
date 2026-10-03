"""The public Python facades: documented imports, filename composition, rename_ops exports, request accessors."""

from __future__ import annotations

from pathlib import Path

import pytest

from folionym import config, filename, heuristics, rename_ops, renamer
from folionym.config import RenamerConfig
from folionym.filename import FilenameGenerationRequest, generate_filename
from folionym.heuristics import CategoryCombineParams
from folionym.llm.models import VisionCompletionOptions
from folionym.naming.models import FilenameGenerationDependencies


def test_documented_python_imports_remain_owned_by_their_public_modules() -> None:
    """Keep the supported import surface stable without reviving compatibility aliases."""
    assert RenamerConfig.__name__ == "RenamerConfig"
    assert FilenameGenerationRequest.__name__ == "FilenameGenerationRequest"
    assert CategoryCombineParams.__name__ == "CategoryCombineParams"
    assert callable(generate_filename)
    assert all(
        callable(getattr(renamer, name))
        for name in (
            "process_one_file",
            "suggest_rename_for_file",
            "produce_rename_results",
            "rename_pdfs_in_directory",
            "run_watch_loop",
        )
    )
    assert not hasattr(renamer, "RenamerConfig")
    assert not hasattr(renamer, "generate_filename")


def test_filename_facade_owns_a_lazy_llm_client_for_direct_composition(monkeypatch: pytest.MonkeyPatch) -> None:
    config = RenamerConfig()
    factory_calls: list[RenamerConfig] = []
    generated_with: list[object] = []
    closed: list[bool] = []

    class OwnedClient:
        def close(self) -> None:
            closed.append(True)

    owned_client = OwnedClient()

    def create_client(received_config: RenamerConfig) -> OwnedClient:
        factory_calls.append(received_config)
        return owned_client

    def generate(_content: str, request: FilenameGenerationRequest) -> tuple[str, dict[str, object]]:
        generated_with.append(request.llm_client)
        return "20260827-document.pdf", {"source": "llm"}

    monkeypatch.setattr("folionym.llm.http.create_llm_client_from_config", create_client)
    monkeypatch.setattr("folionym.filename._generate_filename", generate)

    assert generate_filename("invoice", FilenameGenerationRequest(config=config)) == (
        "20260827-document.pdf",
        {"source": "llm"},
    )
    assert factory_calls == [config]
    assert generated_with == [owned_client]
    assert closed == [True]


def test_filename_facade_preserves_an_injected_llm_client(monkeypatch: pytest.MonkeyPatch) -> None:
    config = RenamerConfig()
    generated_with: list[object] = []
    closed: list[bool] = []

    class InjectedClient:
        model = "injected"
        base_url = ""

        def complete(
            self,
            _prompt: str,
            *,
            temperature: float = 0.0,
            max_tokens: int | None = None,
            response_format: dict[str, str] | None = None,
        ) -> str:
            return ""

        def complete_vision(
            self,
            _image_b64: str,
            _prompt: str,
            options: VisionCompletionOptions | None = None,
        ) -> str:
            return ""

        def close(self) -> None:
            closed.append(True)

    injected_client = InjectedClient()

    def should_not_construct(_config: RenamerConfig) -> object:
        raise AssertionError("injected clients must not trigger HTTP construction")

    def generate(_content: str, request: FilenameGenerationRequest) -> tuple[str, dict[str, object]]:
        generated_with.append(request.llm_client)
        return "20260827-document.pdf", {}

    monkeypatch.setattr("folionym.llm.http.create_llm_client_from_config", should_not_construct)
    monkeypatch.setattr("folionym.filename._generate_filename", generate)

    request = FilenameGenerationRequest(
        config=config,
        dependencies=FilenameGenerationDependencies(llm_client=injected_client),
    )
    assert generate_filename("invoice", request) == ("20260827-document.pdf", {})
    assert generated_with == [injected_client]
    assert closed == []


def test_rename_ops_facade_has_the_complete_supported_export_set() -> None:
    expected = {
        "FILENAME_RESERVED_WIN",
        "FILENAME_UNSAFE_RE",
        "MAX_LLM_FILENAME_LEN",
        "MAX_RENAME_RETRIES",
        "RenameApplyOptions",
        "RenameAttemptState",
        "RenameRetryContext",
        "apply_single_rename",
        "is_path_within",
        "sanitize_filename_base",
        "sanitize_filename_from_llm",
    }
    assert set(rename_ops.__all__) == expected
    assert all(hasattr(rename_ops, export) for export in expected)


def test_config_filename_and_heuristics_facades_pin_their_exports() -> None:
    assert set(config.__all__) == {
        "ExtractionConfig",
        "HeuristicCategoryConfig",
        "HeuristicConfig",
        "HeuristicScoreConfig",
        "HeuristicSkipConfig",
        "HeuristicWindowConfig",
        "LLMBackendConfig",
        "LLMConfig",
        "LLMContentConfig",
        "LLMRuntimeConfig",
        "LLMVisionConfig",
        "OutputConfig",
        "OutputHookConfig",
        "OutputModeConfig",
        "OutputNamingConfig",
        "OutputPathConfig",
        "OutputProgressConfig",
        "OutputTemplateConfig",
        "OutputTraversalConfig",
        "RenamerConfig",
        "build_config",
        "build_config_from_flat_dict",
    }
    assert set(filename.__all__) == {"FilenameGenerationRequest", "generate_filename"}
    assert set(heuristics.__all__) == {"CategoryCombineParams"}


def test_filename_generation_request_exposes_its_documented_accessors(tmp_path: Path) -> None:
    from datetime import date

    from folionym.naming.models import FilenameGenerationContext

    stopwords = frozenset({"und"})
    context = FilenameGenerationContext(
        override_category="invoice",
        today=date(2026, 1, 2),
        pdf_metadata={"title": "x"},
        source_path=tmp_path / "a.pdf",
    )
    request = FilenameGenerationRequest(
        RenamerConfig(), dependencies=FilenameGenerationDependencies(stopwords=stopwords), context=context
    )

    assert request.llm_client is None
    assert request.heuristic_scorer is None
    assert request.stopwords is stopwords
    assert request.override_category == "invoice"
    assert request.today == date(2026, 1, 2)
    assert request.pdf_metadata == {"title": "x"}
    assert request.rules is None
    assert request.source_path == tmp_path / "a.pdf"
