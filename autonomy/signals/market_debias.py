"""Market-debias signal: exploit the exchange's own measured miscalibration.

Prediction markets carry documented systematic biases (the longshot bias
being the classic: cheap contracts resolve YES less often than their price
implies). Instead of assuming the folklore, we measure it: the retro engine
records (market mid, settlement result) for every settled market it can
quote, and `fit_curve` bins those into an empirical price->outcome curve.

The signal then answers one question per market: at this price level, what
fraction of markets ACTUALLY resolved YES? Where that differs from the price,
the market itself is the mispriced instrument.

Fail-closed everywhere: no curve artifact -> signal inapplicable; a price
bucket with fewer than MIN_BUCKET_N observations -> no opinion. The signal
earns trust weight from live settlements like every other source — and the
retro engine deliberately never writes retro signals for this source, so its
weight is never graded on the same window the curve was fit on.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autonomy.ontology import MarketView, Signal

CURVE_PATH = Path("runtime/autonomy/market_calibration.json")
N_BUCKETS = 20  # 5-cent buckets
MIN_BUCKET_N = 100  # no opinion from thin history


def ledger_samples(ledger: Any) -> list[tuple[float, int]]:
    """(market-prior probability, outcome) pairs for every settled market.

    The market_prior signal IS the book's contemporaneous mid, so joining it
    to settlements yields debias samples for free — live and retro alike.
    """
    rows = ledger._conn.execute(  # noqa: SLF001 - trusted ledger consumer
        """
        SELECT s.probability_yes, st.result_yes FROM settlements st
        JOIN signals s ON s.market_ticker = st.market_ticker
        WHERE s.source = 'market_prior'
          AND s.id = (SELECT MAX(id) FROM signals
                      WHERE market_ticker = st.market_ticker AND source = 'market_prior')
        """
    ).fetchall()
    return [(float(p), int(r)) for p, r in rows]


def fit_curve(samples: list[tuple[float, int]]) -> dict[str, Any]:
    """Bin (mid_probability, result) pairs into an empirical calibration curve."""
    buckets = [{"lo": i / N_BUCKETS, "hi": (i + 1) / N_BUCKETS, "n": 0,
                "sum_price": 0.0, "sum_yes": 0} for i in range(N_BUCKETS)]
    for mid_prob, result in samples:
        idx = min(N_BUCKETS - 1, max(0, int(mid_prob * N_BUCKETS)))
        buckets[idx]["n"] += 1
        buckets[idx]["sum_price"] += mid_prob
        buckets[idx]["sum_yes"] += int(result)
    out = []
    for bucket in buckets:
        n = bucket["n"]
        out.append({
            "lo": bucket["lo"], "hi": bucket["hi"], "n": n,
            "avg_price": round(bucket["sum_price"] / n, 4) if n else None,
            "yes_rate": round(bucket["sum_yes"] / n, 4) if n else None,
        })
    return {
        "report_name": "MARKET_DEBIAS_CURVE",
        "n_total": len(samples),
        "min_bucket_n": MIN_BUCKET_N,
        "buckets": out,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def write_curve(curve: dict[str, Any], path: Path | None = None) -> Path:
    path = path or CURVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(curve, indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_curve(path: Path | None = None) -> dict[str, Any] | None:
    path = path or CURVE_PATH
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data.get("buckets"), list) else None


class MarketDebiasSignal:
    name = "market_debias"

    def __init__(self, curve: dict[str, Any] | None = None, curve_path: Path | None = None):
        self._curve = curve if curve is not None else load_curve(curve_path)

    def _bucket_for(self, mid_prob: float) -> dict[str, Any] | None:
        if self._curve is None:
            return None
        idx = min(N_BUCKETS - 1, max(0, int(mid_prob * N_BUCKETS)))
        buckets = self._curve.get("buckets", [])
        if idx >= len(buckets):
            return None
        bucket = buckets[idx]
        if int(bucket.get("n") or 0) < MIN_BUCKET_N or bucket.get("yes_rate") is None:
            return None
        return bucket

    def applicable(self, market: MarketView) -> bool:
        if self._curve is None:
            return False
        return market.yes_bid is not None and market.yes_ask is not None and market.yes_ask > 0

    def generate(self, market: MarketView) -> Signal | None:
        if market.yes_bid is None or market.yes_ask is None:
            return None
        mid_prob = min(0.995, max(0.005, (market.yes_bid + market.yes_ask) / 200.0))
        bucket = self._bucket_for(mid_prob)
        if bucket is None:
            return None
        rate = float(bucket["yes_rate"])
        n = int(bucket["n"])
        # Binomial standard error widens the opinion where history is thinner.
        se = math.sqrt(max(1e-9, rate * (1.0 - rate)) / n)
        p_yes = min(0.995, max(0.005, rate))
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=p_yes,
            uncertainty=min(0.5, max(0.06, 0.08 + 2.0 * se)),
            rationale=(
                f"empirical debias: mid {mid_prob:.2f} bucket "
                f"[{bucket['lo']:.2f},{bucket['hi']:.2f}) resolved YES {rate:.1%} over n={n}"
            ),
            features={"mid_prob": mid_prob, "bucket_n": n, "bucket_yes_rate": rate},
        )
