"""Verified promoted integrations only.

Harvested repositories remain metadata in the incorporation registry until an
adapter-specific implementation and evidence package passes human review.
They are represented by one inert ``PendingAdapter`` in tests and research
tools, not by generated source modules.
"""

from __future__ import annotations

from adapters.promoted.pending import PendingAdapter

PROMOTED_ADAPTER_NAMES: tuple[str, ...] = ()
PROMOTED_MODULES: dict[str, str] = {}

__all__ = ["PROMOTED_ADAPTER_NAMES", "PROMOTED_MODULES", "PendingAdapter"]
