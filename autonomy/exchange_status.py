"""Exchange maintenance awareness: never trade into a closed venue.

Kalshi publishes its own state at /exchange/status (exchange_active,
trading_active) and scheduled downtime at /exchange/schedule
(maintenance_windows). The brain checks once per cycle:

  - exchange_active=False  -> the whole venue is down (maintenance): skip the
    cycle with an honest CYCLE_SKIPPED_EXCHANGE_MAINTENANCE status. No error
    spam, no alert streaks, no pointless scans against a dead API.
  - trading_active=False   -> reads work but orders won't (e.g. the overnight
    trading pause): run the full learning loop (scan, signal, settle, grade)
    but place no orders this cycle.
  - status fetch fails     -> unknown is NOT down: proceed normally and let
    the existing crash-isolated paths handle a real outage. This check must
    never become its own stall point.
"""
from __future__ import annotations

import os
from typing import Any


def _public_base() -> str:
    base = os.environ.get("KALSHI_API_BASE", "https://api.elections.kalshi.com").rstrip("/")
    version = os.environ.get("KALSHI_API_VERSION", "trade-api/v2").strip("/")
    return f"{base}/{version}"


def fetch_exchange_status() -> dict[str, Any]:
    """Current venue state + any scheduled maintenance windows (public GETs)."""
    import httpx

    response = httpx.get(f"{_public_base()}/exchange/status", timeout=10)
    response.raise_for_status()
    status = response.json()
    out: dict[str, Any] = {
        "exchange_active": bool(status.get("exchange_active", True)),
        "trading_active": bool(status.get("trading_active", True)),
        "maintenance_windows": [],
    }
    # Schedule is advisory garnish; its failure never fails the status check.
    try:
        schedule = httpx.get(f"{_public_base()}/exchange/schedule", timeout=10)
        schedule.raise_for_status()
        windows = (schedule.json().get("schedule") or {}).get("maintenance_windows") or []
        out["maintenance_windows"] = windows
    except Exception:
        pass
    return out
