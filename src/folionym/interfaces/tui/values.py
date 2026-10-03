"""Form readers and run-state value access shared by the Textual app controller."""

from __future__ import annotations

import logging
from typing import Any, cast

from textual.css.query import QueryError
from textual.widgets import Checkbox, Input, Select

from ...settings import RenamerConfig
from ..ui_settings import build_config_from_ui_settings
from .presentation import endpoint_disclosure, snapshot_from_readers

logger = logging.getLogger(__name__)


class TuiValueAccess:
    """Keep configuration reads and operation-state values out of the view controller."""

    def get_str(self, widget_id: str, default: str = "") -> str:
        """Read and trim an input value, returning the supplied default on lookup failure."""
        try:
            widget = cast(Any, self).query_one(f"#{widget_id}", Input)
            return str(widget.value).strip()
        except QueryError:
            logger.debug("Widget query failed for #%s (Input)", widget_id)
            return default

    def get_bool(self, widget_id: str, default: bool = False) -> bool:
        """Read a checkbox value, returning the supplied default on lookup failure."""
        try:
            widget = cast(Any, self).query_one(f"#{widget_id}", Checkbox)
            return bool(widget.value)
        except QueryError:
            logger.debug("Widget query failed for #%s (Checkbox)", widget_id)
            return default

    def get_select(self, widget_id: str, default: str = "") -> str:
        """Read a select value, returning the supplied default for blank or missing widgets."""
        try:
            value = cast(Any, self).query_one(f"#{widget_id}", Select).value
            return str(value) if value is not Select.BLANK else default
        except QueryError:
            logger.debug("Widget query failed for #%s (Select)", widget_id)
            return default

    def snapshot(self) -> dict[str, object]:
        """Collect the current form values in the persisted settings shape."""
        return snapshot_from_readers(self.get_str, self.get_bool, self.get_select)

    def build_config(self, *, dry_run: bool, manual_mode: bool = False) -> RenamerConfig:
        """Build a rename configuration from the current form snapshot."""
        app = cast(Any, self)
        return build_config_from_ui_settings(self.snapshot(), app._stop_event, dry_run=dry_run, manual_mode=manual_mode)

    def _endpoint_disclosure(self) -> tuple[str, str]:
        """Describe whether the model endpoint the next run would contact is local or external."""
        try:
            config: RenamerConfig | None = self.build_config(dry_run=True)
        except ValueError:
            config = None
        return endpoint_disclosure(config)
