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
from datetime import date

FEE_SCHEDULE_EFFECTIVE_DATE = date(2026, 7, 7)
FEE_SCHEDULE_MAX_AGE_DAYS = 31
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


def series_ticker(market_ticker: str | None) -> str:
    return str(market_ticker or "").split("-", 1)[0].upper()


def fee_schedule_is_fresh(as_of: date | None = None) -> bool:
    age = ((as_of or date.today()) - FEE_SCHEDULE_EFFECTIVE_DATE).days
    return 0 <= age <= FEE_SCHEDULE_MAX_AGE_DAYS


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
    if not fee_schedule_is_fresh(as_of):
        return kalshi_taker_fee_cents(price_cents, count, market_ticker)
    series = series_ticker(market_ticker)
    if series in ZERO_FEE_SERIES:
        return 0
    multiplier = 1 if series in MAKER_FEE_SERIES else 0
    return _fee_cents(price_cents, count, rate=0.0175, multiplier=multiplier)
