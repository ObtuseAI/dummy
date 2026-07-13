"""Council snapshot: persists live-registry health for the dashboard (WS-13).

The operator dashboard (autonomy/dashboard.py) is a query-only process that
reads runtime JSON files; it never constructs a live ``SpecialistRegistry``.
The mispricing monitor (scripts/run_dummy_mispricing_monitor.py) already
builds and cycles a live council every pass (90s/2min cadence), so it is the
natural writer: this module is the PURE assembly function (no I/O, easy to
unit test) the script calls once per full sweep, then atomic-writes to
``runtime/autonomy/council_snapshot.json``.

Fail-closed by construction:
  * ``SpecialistRegistry.health_report()`` is already exception-guarded per
    specialist (autonomy/specialists/base.py) -- one broken vertical never
    takes the snapshot down.
  * A ticker this pass can't attribute to any specialist (``None``/absent in
    ``ticker_specialist``) is simply not counted against any row, never
    raises.
  * If this module is never called (writer not wired, or the monitor is
    down), the dashboard's council panel just reads no file and renders
    empty -- exactly like every other file-backed panel.

This is read-only reporting: it introduces no new pricing, allocation, or
execution path and changes no engine's decisions.
"""
from __future__ import annotations

from typing import Any


def build_council_snapshot(
    council: Any,
    report: dict[str, Any],
    ticker_specialist: dict[str, str | None],
    now_iso: str,
) -> dict[str, Any]:
    """Assemble the persisted council snapshot from one live monitor pass.

    ``council`` is the live ``SpecialistRegistry`` the monitor already built
    for this pass. ``report`` is this pass's ``run_mispricing_sweep()``
    output -- only its ``opportunities`` list is used here (ticker/side/etc),
    to derive a per-specialist open-opportunities count. ``ticker_specialist``
    maps this pass's scanned ticker -> the council's routing label for it
    (``Specialist.name``); a ticker with no entry or a ``None`` label is
    simply not attributed to any specialist.
    """
    opportunities = report.get("opportunities") or []
    open_counts: dict[str, int] = {}
    for opportunity in opportunities:
        label = ticker_specialist.get((opportunity or {}).get("ticker"))
        if label:
            open_counts[label] = open_counts.get(label, 0) + 1

    specialists: list[dict[str, Any]] = []
    for entry in council.health_report():
        name = entry.get("name")
        specialists.append({
            **entry,
            "open_opportunities": open_counts.get(name, 0),
        })

    return {
        "generated_at": now_iso,
        "specialists": specialists,
    }
