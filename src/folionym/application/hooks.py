"""Post-rename side effects for the batch renamer."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..extraction.writer import write_document_metadata
from ..infrastructure.http import HttpRequestError, post_json_without_redirects, validate_http_endpoint
from ..settings import RenamerConfig
from ..settings.environment import ENV_POST_RENAME_HOOK, env_str
from .artifacts import append_export_row
from .rename_log import append_rename_log_entry

logger = logging.getLogger(__name__)


@dataclass
class PostRenameAction:
    """Inputs for post-rename logging, metadata, export, and hook side effects."""

    file_path: Path
    target: Path
    current_base: str
    meta: dict[str, object]
    export_rows: list[dict[str, object]]


def _validated_hook_url(value: str) -> str:
    """Return a safe HTTP(S) hook URL or raise a value-only validation error."""
    endpoint = validate_http_endpoint(value)
    if endpoint.scheme == "http" and not endpoint.is_literal_loopback:
        raise ValueError("unencrypted plain HTTP requires a literal loopback IP address")
    return endpoint.url


def _post_hook_http(url: str, old_path: Path, new_path: Path, meta: dict[str, object]) -> None:
    """POST the rename payload; transport safety lives in ``post_json_without_redirects``."""
    payload: dict[str, object] = {
        "old_path": str(old_path),
        "new_path": str(new_path),
        "meta": meta,
    }
    post_json_without_redirects(url, payload, timeout=10)


def _warn_local_hook_disabled() -> None:
    """Warn that local command hooks are disabled."""
    logger.warning(
        "Local post-rename hook commands are disabled and were not run. "
        "Configure an HTTPS post-rename hook endpoint instead."
    )


def run_post_rename_hook(hook_cmd: str, old_path: Path, new_path: Path, meta: dict[str, object]) -> None:
    """Run post-rename HTTP endpoint. Local command hooks are rejected."""
    cmd = (hook_cmd or "").strip()
    if not cmd:
        return
    # fmt: off
    try:
        if "://" not in cmd:
            _warn_local_hook_disabled()
            return
        validated_url = _validated_hook_url(cmd)
        _post_hook_http(validated_url, old_path, new_path, meta)
    except ValueError as exc:
        logger.warning("Post-rename hook URL rejected: %s.", exc)
    except HttpRequestError:
        logger.warning("Post-rename hook HTTP call failed.")
    except (AttributeError, OSError, TypeError):
        logger.warning("Post-rename hook failed.")
    # fmt: on


def _configured_hook_command(config: RenamerConfig) -> str:
    """Return the configured hook URL, preferring explicit configuration over the environment."""
    configured = (config.output.hooks.post_rename_hook or "").strip()
    return configured or env_str(ENV_POST_RENAME_HOOK) or ""


def _apply_post_rename_actions(
    config: RenamerConfig,
    action: PostRenameAction,
) -> None:
    """Write rename log, PDF metadata, and export row after a successful rename."""
    paths = config.output.paths
    if paths.export_metadata_path:
        append_export_row(action.export_rows, file_path=action.file_path, target=action.target, meta=action.meta)
    if paths.rename_log_path:
        append_rename_log_entry(paths.rename_log_path, action.file_path, action.target)
    if config.output.mode.write_pdf_metadata:
        write_document_metadata(action.target, action.current_base)
    hook_cmd = _configured_hook_command(config)
    if hook_cmd:
        run_post_rename_hook(hook_cmd, action.file_path, action.target, action.meta)


def make_post_rename_success_callback(
    config: RenamerConfig,
    meta: dict[str, object] | None,
    export_rows: list[dict[str, object]],
) -> Callable[[Path, Path, str], None]:
    """Capture metadata and export state in a post-rename side-effect callback."""
    current_meta = meta or {}

    def _on_rename_success(_fp: Path, _target: Path, _current_base: str) -> None:
        """Apply configured post-rename actions after a completed rename."""
        _apply_post_rename_actions(
            config,
            PostRenameAction(_fp, _target, _current_base, current_meta, export_rows),
        )

    return _on_rename_success
