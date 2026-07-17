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
# Per-vertical curves (Wave-6 lean-in). The pooled curve is dominated ~100:1
# by crypto samples, so the measured SPORTS bias (the system's strongest
# demonstrated edge: +0.089 contested Brier edge on MLB, CI95 positive, 96
# clusters) was being read off a crypto-shaped curve. Vertical curves use
# coarser 10-cent buckets with a lower per-bucket floor so a season's worth
# of sports settlements is dense enough to speak, while the global curve
# keeps its original geometry as the fallback.
N_VERTICAL_BUCKETS = 10
MIN_VERTICAL_BUCKET_N = 80


def ledger_samples(ledger: Any) -> list[tuple[float, int, str]]:
    """(market-prior probability, outcome, ticker) for every settled market.

    The market_prior signal IS the book's contemporaneous mid, so joining it
    to settlements yields debias samples for free — live and retro alike.
    The ticker rides along so the curve can be partitioned by vertical.
    """
    rows = ledger._conn.execute(  # noqa: SLF001 - trusted ledger consumer
        """
        SELECT s.probability_yes, st.result_yes, st.market_ticker FROM settlements st
        JOIN signal_history s ON s.market_ticker = st.market_ticker
        WHERE s.source = 'market_prior'
          AND s.id = (SELECT MAX(id) FROM signal_history
                      WHERE market_ticker = st.market_ticker AND source = 'market_prior')
        """
    ).fetchall()
    return [(float(p), int(r), str(t)) for p, r, t in rows]


def _bin_samples(
    samples: list[tuple[float, int]], n_buckets: int,
) -> list[dict[str, Any]]:
    buckets = [{"lo": i / n_buckets, "hi": (i + 1) / n_buckets, "n": 0,
                "sum_price": 0.0, "sum_yes": 0} for i in range(n_buckets)]
    for mid_prob, result in samples:
        idx = min(n_buckets - 1, max(0, int(mid_prob * n_buckets)))
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
    return out


def fit_curve(samples: list[tuple]) -> dict[str, Any]:
    """Bin samples into the global curve plus per-vertical curves.

    Accepts 2-tuples ``(mid_probability, result)`` (legacy retro candle
    samples — global curve only) and 3-tuples ``(mid_probability, result,
    ticker)`` (partitioned into a per-vertical curve as well). The artifact
    stays backward-compatible: the top-level ``buckets`` is the global curve
    every existing reader understands; ``verticals`` is additive.
    """
    flat: list[tuple[float, int]] = []
    by_vertical: dict[str, list[tuple[float, int]]] = {}
    for sample in samples:
        mid_prob, result = float(sample[0]), int(sample[1])
        flat.append((mid_prob, result))
        if len(sample) >= 3 and sample[2]:
            try:
                from autonomy.scanner import classify_vertical

                vertical = classify_vertical(str(sample[2])).value
            except Exception:
                continue
            by_vertical.setdefault(vertical, []).append((mid_prob, result))
    verticals = {
        vertical: {
            "n_total": len(rows),
            "n_buckets": N_VERTICAL_BUCKETS,
            "min_bucket_n": MIN_VERTICAL_BUCKET_N,
            "buckets": _bin_samples(rows, N_VERTICAL_BUCKETS),
        }
        for vertical, rows in sorted(by_vertical.items())
    }
    return {
        "report_name": "MARKET_DEBIAS_CURVE",
        "schema_version": 2,
        "n_total": len(flat),
        "min_bucket_n": MIN_BUCKET_N,
        "buckets": _bin_samples(flat, N_BUCKETS),
        "verticals": verticals,
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

    def _bucket_for(self, mid_prob: float, vertical: str | None = None) -> tuple[dict[str, Any], str] | None:
        """(bucket, curve_scope) — the vertical's own curve when it is dense
        enough at this price level, else the pooled global curve."""
        if self._curve is None:
            return None
        if vertical:
            vertical_curve = (self._curve.get("verticals") or {}).get(vertical)
            if isinstance(vertical_curve, dict):
                n_buckets = int(vertical_curve.get("n_buckets") or N_VERTICAL_BUCKETS)
                min_n = int(vertical_curve.get("min_bucket_n") or MIN_VERTICAL_BUCKET_N)
                buckets = vertical_curve.get("buckets") or []
                idx = min(n_buckets - 1, max(0, int(mid_prob * n_buckets)))
                if idx < len(buckets):
                    bucket = buckets[idx]
                    if int(bucket.get("n") or 0) >= min_n and bucket.get("yes_rate") is not None:
                        return bucket, vertical
        idx = min(N_BUCKETS - 1, max(0, int(mid_prob * N_BUCKETS)))
        buckets = self._curve.get("buckets", [])
        if idx >= len(buckets):
            return None
        bucket = buckets[idx]
        if int(bucket.get("n") or 0) < MIN_BUCKET_N or bucket.get("yes_rate") is None:
            return None
        return bucket, "global"

    def applicable(self, market: MarketView) -> bool:
        if self._curve is None:
            return False
        from autonomy.quote_quality import honest_implied_yes

        return honest_implied_yes(market.yes_bid, market.yes_ask) is not None

    def generate(self, market: MarketView) -> Signal | None:
        # Honest-quote gate (Wave-5 discipline): a phantom mid on a dead book
        # is not a price level; opining on it would re-import the fabrication
        # the measurement layer just evicted.
        from autonomy.quote_quality import honest_implied_yes

        implied = honest_implied_yes(market.yes_bid, market.yes_ask)
        if implied is None:
            return None
        mid_prob = min(0.995, max(0.005, implied))
        found = self._bucket_for(mid_prob, market.vertical.value)
        if found is None:
            return None
        bucket, curve_scope = found
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
                f"empirical debias[{curve_scope}]: mid {mid_prob:.2f} bucket "
                f"[{bucket['lo']:.2f},{bucket['hi']:.2f}) resolved YES {rate:.1%} over n={n}"
            ),
            features={
                "mid_prob": mid_prob, "bucket_n": n, "bucket_yes_rate": rate,
                "curve_scope": curve_scope,
            },
        )
