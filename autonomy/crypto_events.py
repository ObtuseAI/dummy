"""Scheduled macro event windows that widen crypto forecast uncertainty.

Crypto realized volatility clusters around scheduled macro releases; a model
calibrated on quiet hours is overconfident through an FOMC decision. This
module keeps a small, static, auditable calendar of such windows and exposes
a bounded uncertainty bump the crypto models add while a window is active.

Doctrine:
  * The bump WIDENS uncertainty only -- it never shifts the mean (we know the
    event's timing, not its direction).
  * Fail-closed: outside every window (or with an empty table) the bump is
    exactly 0.0 and forecasts are byte-identical to a build without this
    module.
  * Static and auditable on purpose: entries are shipped in code review, not
    scraped at runtime. Only calendars known with certainty belong here --
    the 2026 FOMC meeting dates below are the Federal Reserve's published
    schedule. CPI/unlock entries can be added the same way when curated.
"""
from __future__ import annotations

from datetime import datetime, timezone

# Bounded uncertainty bump while inside any window. Combined with the base
# crypto uncertainty this stays inside the model's 0.35 ceiling.
EVENT_UNCERTAINTY_BUMP = 0.04

# (label, start_utc_iso, end_utc_iso) -- inclusive start, exclusive end.
# FOMC windows cover both meeting days through the end of the decision day
# (statement 18:00Z + press conference + immediate repricing).
EVENT_WINDOWS: tuple[tuple[str, str, str], ...] = (
    ("FOMC", "2026-01-27T00:00:00+00:00", "2026-01-29T00:00:00+00:00"),
    ("FOMC", "2026-03-17T00:00:00+00:00", "2026-03-19T00:00:00+00:00"),
    ("FOMC", "2026-04-28T00:00:00+00:00", "2026-04-30T00:00:00+00:00"),
    ("FOMC", "2026-06-16T00:00:00+00:00", "2026-06-18T00:00:00+00:00"),
    ("FOMC", "2026-07-28T00:00:00+00:00", "2026-07-30T00:00:00+00:00"),
    ("FOMC", "2026-09-15T00:00:00+00:00", "2026-09-17T00:00:00+00:00"),
    ("FOMC", "2026-10-27T00:00:00+00:00", "2026-10-29T00:00:00+00:00"),
    ("FOMC", "2026-12-08T00:00:00+00:00", "2026-12-10T00:00:00+00:00"),
)


def active_event(now: datetime | None = None) -> str | None:
    """Label of the active event window, or None (the common case)."""
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    for label, start_iso, end_iso in EVENT_WINDOWS:
        try:
            start = datetime.fromisoformat(start_iso)
            end = datetime.fromisoformat(end_iso)
        except ValueError:
            continue  # a malformed entry must never break forecasting
        if start <= moment < end:
            return label
    return None


def active_bump(now: datetime | None = None) -> float:
    """Uncertainty bump for the current moment: EVENT_UNCERTAINTY_BUMP or 0.0."""
    return EVENT_UNCERTAINTY_BUMP if active_event(now) is not None else 0.0
