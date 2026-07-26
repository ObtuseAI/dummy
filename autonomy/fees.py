"""Current Kalshi event-contract fee model used by the autonomy loop.

Dummy submits edge-preserving resting LIMIT orders.  Those fills are maker
fills unless the fresh-quote guard detects a crossed book and blocks the
submission.  Treating every fill as a taker fill understates maker EV and
distorts both selection and realized P&L.

The non-standard series set below is from Kalshi's fee schedule effective
2026-07-07.  The schedule is intentionally time-bounded: when it becomes
stale, maker estimates fail closed to the (higher) general taker fee until the
list is refreshed.
"""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from datetime import date, timedelta

FEE_SCHEDULE_EFFECTIVE_DATE = date(2026, 7, 7)
FEE_SCHEDULE_MAX_AGE_DAYS = 31
FEE_SCHEDULE_REFRESH_WARNING_DAYS = 7
FEE_SCHEDULE_URL = "https://kalshi.com/docs/kalshi-fee-schedule.pdf"

# Series with maker multiplier M=1 in the 2026-07-07 fee schedule.  All
# unlisted event-contract series use the general maker multiplier M=0 while
# this schedule is fresh.
MAKER_FEE_SERIES = frozenset({
    "KXAAAGASM", "KXATPMATCH", "KXBALLONDOR", "KXBTCMAX150", "KXCPI",
    "KXCPIYOY", "KXEGGS", "KXEMMYCACTO", "KXEMMYCACTR", "KXEMMYCSERIES",
    "KXEMMYDACTO", "KXEMMYDACTR", "KXEMMYDSERIES", "KXFED",
    "KXFEDDECISION", "KXGDP", "KXHEISMAN", "KXINXY", "KXIPO", "KXLALIGA",
    "KXLLM1", "KXMARMAD", "KXMENWORLDCUP", "KXMLB", "KXMLBAL",
    "KXMLBASGAME", "KXMLBGAME", "KXMLBNL", "KXNASDAQ100Y", "KXNBA",
    "KXNBAEAST", "KXNBAMVP", "KXNBAROY", "KXNBAWEST", "KXNCAAF",
    "KXNCAAFACC", "KXNCAAFB10", "KXNCAAFB12", "KXNCAAFGAME",
    "KXNCAAFPLAYOFF", "KXNCAAFSEC", "KXNFLAFCCHAMP", "KXNFLAFCEAST",
    "KXNFLAFCNORTH", "KXNFLAFCSOUTH", "KXNFLAFCWEST", "KXNFLCOTY",
    "KXNFLCPOTY", "KXNFLDPOTY", "KXNFLDROTY", "KXNFLGAME", "KXNFLMVP",
    "KXNFLNFCCHAMP", "KXNFLNFCEAST", "KXNFLNFCNORTH", "KXNFLNFCSOUTH",
    "KXNFLNFCWEST", "KXNFLOPOTY", "KXNFLOROTY", "KXNHL", "KXNHLEAST",
    "KXNHLWEST", "KXPAYROLLS", "KXPGARYDER", "KXPGASOLHEIM", "KXPGATOUR",
    "KXRATECUTCOUNT", "KXSB", "KXSUPERBOWLHEADLINE", "KXU3", "KXUCL",
    "KXUCLGAME", "KXWCGAME", "KXWNBA", "KXWNBAGAME", "KXWTAMATCH",
})

# Explicit non-standard zero-fee series (maker and taker multiplier M=0).
ZERO_FEE_SERIES = frozenset({
    "KXBTCY", "KXCITRINI", "KXDOED", "KXELECTIRAN", "KXETHY",
    "KXGAMBLINGREPEAL", "KXGREENLAND", "KXIRANDEMOCRACY",
    "KXLAYOFFSYINFO", "KXPAHLAVIHEAD",
})


class FeeScheduleRefreshWarning(UserWarning):
    """An embedded fee schedule is approaching its fail-closed date."""


@dataclass(frozen=True)
class FeeScheduleFreshness:
    as_of: date
    effective_date: date
    last_fresh_date: date
    fail_closed_from: date
    age_days: int
    days_until_last_fresh_date: int
    days_until_fail_closed: int
    fresh: bool
    refresh_recommended: bool
    status: str
    warning: str | None
    source_url: str


def series_ticker(market_ticker: str | None) -> str:
    return str(market_ticker or "").split("-", 1)[0].upper()


def fee_schedule_freshness(as_of: date | None = None) -> FeeScheduleFreshness:
    """Return local schedule age and a pre-cliff refresh warning without I/O."""
    current_date = as_of or date.today()
    age_days = (current_date - FEE_SCHEDULE_EFFECTIVE_DATE).days
    last_fresh_date = FEE_SCHEDULE_EFFECTIVE_DATE + timedelta(
        days=FEE_SCHEDULE_MAX_AGE_DAYS
    )
    fail_closed_from = last_fresh_date + timedelta(days=1)
    days_until_last_fresh_date = (last_fresh_date - current_date).days
    days_until_fail_closed = (fail_closed_from - current_date).days
    fresh = 0 <= age_days <= FEE_SCHEDULE_MAX_AGE_DAYS

    warning: str | None = None
    if age_days < 0:
        status = "NOT_YET_EFFECTIVE"
        refresh_recommended = False
        warning = (
            f"embedded fee schedule is not effective until "
            f"{FEE_SCHEDULE_EFFECTIVE_DATE.isoformat()}; maker pricing fails closed"
        )
    elif not fresh:
        status = "STALE"
        refresh_recommended = True
        warning = (
            f"embedded fee schedule has been stale since "
            f"{fail_closed_from.isoformat()}; maker pricing is failing closed to taker; "
            f"validate a replacement from {FEE_SCHEDULE_URL}"
        )
    elif days_until_last_fresh_date <= FEE_SCHEDULE_REFRESH_WARNING_DAYS:
        status = "REFRESH_DUE"
        refresh_recommended = True
        warning = (
            f"embedded fee schedule reaches its last fresh date on "
            f"{last_fresh_date.isoformat()} and fails closed from "
            f"{fail_closed_from.isoformat()}; validate a replacement from "
            f"{FEE_SCHEDULE_URL}"
        )
    else:
        status = "FRESH"
        refresh_recommended = False

    return FeeScheduleFreshness(
        as_of=current_date,
        effective_date=FEE_SCHEDULE_EFFECTIVE_DATE,
        last_fresh_date=last_fresh_date,
        fail_closed_from=fail_closed_from,
        age_days=age_days,
        days_until_last_fresh_date=days_until_last_fresh_date,
        days_until_fail_closed=days_until_fail_closed,
        fresh=fresh,
        refresh_recommended=refresh_recommended,
        status=status,
        warning=warning,
        source_url=FEE_SCHEDULE_URL,
    )


def fee_schedule_refresh_warning(as_of: date | None = None) -> str | None:
    """Return the operator-facing refresh warning, if any, without network access."""
    return fee_schedule_freshness(as_of).warning


def fee_schedule_is_fresh(as_of: date | None = None) -> bool:
    return fee_schedule_freshness(as_of).fresh


def _fee_cents(price_cents: int, count: int, rate: float, multiplier: int) -> int:
    if count <= 0 or multiplier <= 0 or not (1 <= price_cents <= 99):
        return 0
    p = price_cents / 100.0
    # The published formula is in dollars. Multiplying by 100 returns cents;
    # ceil matches Kalshi's per-order fee table for whole-cent contracts.
    raw_cents = 100.0 * multiplier * rate * count * p * (1.0 - p)
    return math.ceil(raw_cents - 1e-12)


def kalshi_taker_fee_cents(
    price_cents: int,
    count: int,
    market_ticker: str | None = None,
) -> int:
    multiplier = 0 if series_ticker(market_ticker) in ZERO_FEE_SERIES else 1
    return _fee_cents(price_cents, count, rate=0.07, multiplier=multiplier)


def kalshi_maker_fee_cents(
    price_cents: int,
    count: int,
    market_ticker: str | None = None,
    *,
    as_of: date | None = None,
) -> int:
    """Maker fee for a resting order; stale schedules fall back to taker."""
    freshness = fee_schedule_freshness(as_of)
    if freshness.status == "REFRESH_DUE" and freshness.warning:
        warnings.warn(
            freshness.warning,
            FeeScheduleRefreshWarning,
            stacklevel=2,
        )
    if not freshness.fresh:
        return kalshi_taker_fee_cents(price_cents, count, market_ticker)
    series = series_ticker(market_ticker)
    if series in ZERO_FEE_SERIES:
        return 0
    multiplier = 1 if series in MAKER_FEE_SERIES else 0
    return _fee_cents(price_cents, count, rate=0.0175, multiplier=multiplier)
