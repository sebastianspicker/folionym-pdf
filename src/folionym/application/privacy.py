"""Content-boundary decisions shared by the interfaces."""

from __future__ import annotations

from ..infrastructure.http import validate_http_endpoint
from ..settings import RenamerConfig
from ..settings.environment import ENV_LLM_URL, env_str


def run_contacts_model(config: RenamerConfig) -> bool:
    """Return whether a run with this configuration can make an LLM or vision request."""
    return bool(config.llm.runtime.use_llm or config.llm.vision.vision_first or config.llm.vision.use_vision_fallback)


def external_llm_endpoint(config: RenamerConfig) -> str | None:
    """Return the normalized model URL when a run would send content off this machine.

    The endpoint is the one the run will contact: the resolved configuration
    value, else ``FOLIONYM_LLM_URL`` for configurations built without
    ``build_config``. Returns ``None`` when the run makes no model or vision
    request, no endpoint is set (the local default applies), or the endpoint is
    loopback. Raises ``ValueError`` when the endpoint is not a valid HTTP endpoint.
    """
    if not run_contacts_model(config):
        return None
    llm_url = (config.llm.backend.llm_base_url or "").strip() or env_str(ENV_LLM_URL)
    if llm_url is None:
        return None
    endpoint = validate_http_endpoint(llm_url)
    return None if endpoint.is_loopback else endpoint.url
