"""Fail-closed stale-data gate for order submission.

A resting maker edge computed against a book snapshot -- or a price-feed
candle -- that has since gone stale is not an edge; it is standing adverse
selection. The executor refuses to submit any order whose driving snapshot is
older than a per-horizon maximum age.

Defaults are deliberately tight for the fast crypto buckets (a 15-minute BTC
contract re-prices its fair value in well under a minute) and looser for slow
pregame sports markets. They are picked to be defensible, not clever:

  * crypto 15m (and faster)  -> 60s   (matches the one-minute resting-quote TTL
                                       the executor already leases fast crypto)
  * crypto hourly / longer   -> 180s  (an hourly bucket still drifts in minutes)
  * sports live / in-play    -> 120s  (live win-prob moves on every play)
  * sports pregame           -> 300s  (a pregame line is comparatively stable)
  * everything else          -> 300s  (conservative default)

Fail-closed contract: when the gate is active (a policy is supplied) and the
driving snapshot timestamp is missing, unparseable, or in the future, the
order is refused -- unknown freshness is treated as stale, never as fresh.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class StalenessPolicy:
    """Per-horizon maximum driving-snapshot age (seconds) at submit time."""

    crypto_fast_seconds: float = 60.0
    crypto_slow_seconds: float = 180.0
    sports_live_seconds: float = 120.0
    sports_pregame_seconds: float = 300.0
    default_seconds: float = 300.0

    def max_age_seconds(self, ticker: str, *, is_live_market: bool = False) -> float:
        """Resolve the maximum tolerated snapshot age for one market."""
        from autonomy.ontology import Vertical
        from autonomy.scanner import classify_vertical

        vertical = classify_vertical(ticker)
        if vertical is Vertical.CRYPTO:
            return self.crypto_fast_seconds if _is_fast_crypto(ticker) else self.crypto_slow_seconds
        if vertical is Vertical.SPORTS:
            return self.sports_live_seconds if is_live_market else self.sports_pregame_seconds
        return self.default_seconds


DEFAULT_STALENESS_POLICY = StalenessPolicy()


def _is_fast_crypto(ticker: str) -> bool:
    """15-minute (or faster) crypto series carry a 15M cadence tag."""
    upper = ticker.upper()
    return "15M" in upper or "5M" in upper or "1M" in upper


def to_epoch_seconds(value: Any) -> float | None:
    """Parse an ISO-8601 string or numeric epoch into UTC epoch seconds.

    Returns None for anything unparseable so the caller can fail closed.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        text = str(value).strip()
        if not text:
            return None
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (TypeError, ValueError):
        return None


def evaluate_snapshot_freshness(
    ticker: str,
    snapshot_ts: Any,
    now_epoch: float,
    *,
    is_live_market: bool = False,
    policy: StalenessPolicy | None = None,
) -> dict[str, Any]:
    """Decide whether the driving snapshot is fresh enough to submit.

    ``snapshot_ts`` may be an ISO string, an epoch number, or None. Returns a
    detail dict with ``fresh`` (bool), ``reason`` (str), ``age_seconds`` and
    ``max_age_seconds``. Fail-closed: a missing/unparseable/future timestamp is
    reported as not fresh.
    """
    pol = policy or DEFAULT_STALENESS_POLICY
    max_age = pol.max_age_seconds(ticker, is_live_market=is_live_market)
    epoch = to_epoch_seconds(snapshot_ts)
    if epoch is None:
        return {
            "fresh": False,
            "reason": "missing_snapshot_timestamp",
            "age_seconds": None,
            "max_age_seconds": max_age,
        }
    age = now_epoch - epoch
    if age < -1.0:
        # A timestamp meaningfully in the future signals a clock/plumbing fault.
        return {
            "fresh": False,
            "reason": "snapshot_timestamp_in_future",
            "age_seconds": round(age, 3),
            "max_age_seconds": max_age,
        }
    fresh = age <= max_age
    return {
        "fresh": fresh,
        "reason": "fresh" if fresh else "stale_market_snapshot",
        "age_seconds": round(age, 3),
        "max_age_seconds": max_age,
    }
