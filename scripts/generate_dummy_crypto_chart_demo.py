"""Generate an offline, synthetic crypto-chart artifact for UI demonstrations.

This command never contacts a provider.  Its candles are deterministic display
fixtures, not market data, forecast evidence, execution evidence, or authority.
"""
from __future__ import annotations

import argparse
import math
import time
from pathlib import Path

from autonomy.market_observer.artifacts import ContentAddressedArtifactStore
from autonomy.market_observer.contracts import (
    ALLOWED_ASSETS,
    ALLOWED_TIMEFRAMES,
    CandleBar,
    ChartBundle,
    ObservationEnvelope,
    ObservationStatus,
    SourceProvenance,
    sha256_json,
)

_INTERVAL_SECONDS = {
    "15m": 15 * 60,
    "1h": 60 * 60,
    "4h": 4 * 60 * 60,
    "1d": 24 * 60 * 60,
    "1w": 7 * 24 * 60 * 60,
}
_BASE_PRICE = {"BTC": 67_500.0, "ETH": 3_450.0, "SOL": 168.0}


def build_demo_observation(
    asset: str = "BTC",
    timeframe: str = "1h",
    *,
    now_s: float | None = None,
    bar_count: int = 96,
) -> ObservationEnvelope:
    """Build a facts-only synthetic chart envelope with all authority false."""
    normalized_asset = str(asset).upper()
    normalized_timeframe = str(timeframe)
    if normalized_asset not in ALLOWED_ASSETS:
        raise ValueError(f"unsupported asset: {normalized_asset}")
    if normalized_timeframe not in ALLOWED_TIMEFRAMES:
        raise ValueError(f"unsupported timeframe: {normalized_timeframe}")
    if not 30 <= int(bar_count) <= 200:
        raise ValueError("bar_count must be between 30 and 200")

    received_at_s = float(time.time() if now_s is None else now_s)
    interval_s = _INTERVAL_SECONDS[normalized_timeframe]
    last_close_s = int(received_at_s // interval_s) * interval_s
    first_open_s = last_close_s - int(bar_count) * interval_s
    base = _BASE_PRICE[normalized_asset]
    prior_close = base
    candles: list[CandleBar] = []

    for index in range(int(bar_count)):
        open_time_s = first_open_s + index * interval_s
        trend = base * 0.00072 * index
        wave = base * (
            0.012 * math.sin(index / 5.8)
            + 0.0045 * math.sin(index / 2.15)
        )
        close = base + trend + wave
        open_price = prior_close
        wick = base * (0.0024 + 0.0012 * abs(math.sin(index * 1.7)))
        high = max(open_price, close) + wick
        low = min(open_price, close) - wick * 0.85
        volume = 920.0 + 250.0 * (1.0 + math.sin(index / 4.1))
        raw_row = {
            "fixture": "dummy-synthetic-release-demo-v1",
            "asset": normalized_asset,
            "timeframe": normalized_timeframe,
            "index": index,
            "open": round(open_price, 8),
            "high": round(high, 8),
            "low": round(low, 8),
            "close": round(close, 8),
            "volume": round(volume, 8),
        }
        candles.append(
            CandleBar(
                asset=normalized_asset,
                venue="synthetic-demo",
                timeframe=normalized_timeframe,
                interval_s=interval_s,
                open_time_s=open_time_s,
                close_time_s=open_time_s + interval_s,
                received_at_s=received_at_s,
                open=raw_row["open"],
                high=raw_row["high"],
                low=raw_row["low"],
                close=raw_row["close"],
                volume=raw_row["volume"],
                source="dummy-synthetic-release-demo-v1",
                raw_sha256=sha256_json(raw_row),
            )
        )
        prior_close = close

    bundle_identity = sha256_json(
        {
            "fixture": "dummy-synthetic-release-demo-v1",
            "asset": normalized_asset,
            "timeframe": normalized_timeframe,
            "bar_count": len(candles),
        }
    )
    bundle = ChartBundle(
        asset=normalized_asset,
        timeframe=normalized_timeframe,
        generated_at_s=received_at_s,
        candles=tuple(candles),
        indicators={
            "rsi_wilder_14": 58.7,
            "atr_14": round(base * 0.0092, 4),
            "ema_channel_trend": 1.0,
            "atr_normalized_momentum_10": 0.64,
            "macd_atr": 0.37,
            "bollinger_pct_b_20": 0.71,
            "stochastic_k_14": 64.8,
            "obv_slope_20": 0.42,
            "volume_z_20": 0.83,
            "breakout_state": 1.0,
            "fakeout_state": 0.0,
            "close_location_value": 0.62,
        },
        patterns=(
            {
                "name": "synthetic momentum",
                "direction": "up",
                "strength": 0.74,
                "bar_open_time_s": candles[-1].open_time_s,
                "bar_close_time_s": candles[-1].close_time_s,
            },
        ),
        observation_id=bundle_identity,
    )
    return ObservationEnvelope(
        kind="chart_bundle",
        status=ObservationStatus.COMPLETE,
        requested_at_s=received_at_s,
        received_at_s=received_at_s,
        requested={
            "asset": normalized_asset,
            "timeframe": normalized_timeframe,
            "limit": int(bar_count),
        },
        resolved={
            "asset": normalized_asset,
            "timeframe": normalized_timeframe,
            "venue": "synthetic-demo",
            "bar_count": len(candles),
            "latest_close_time_s": candles[-1].close_time_s,
        },
        source=SourceProvenance(
            provider="dummy-synthetic-release-demo",
            venue="synthetic-demo",
            endpoint="https://example.invalid/dummy-synthetic-release-demo",
            documentation_url="https://github.com/obtuseai/dummy",
            adapter_version="dummy-synthetic-release-demo-v1",
            rights_identifier="dummy-self-generated-fixture-v1",
            terms_review_identifier="dummy-synthetic-no-provider-v1",
            terms_url="https://github.com/obtuseai/dummy/blob/main/LICENSE",
            automated_use_permitted=True,
        ),
        payload={"chart_bundle": bundle.to_dict()},
        warnings=(
            "SYNTHETIC DEMO - NOT MARKET DATA OR MARKET EVIDENCE",
            "NO FORECAST, EXECUTION, ALLOCATION, OR PROMOTION AUTHORITY",
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", choices=sorted(ALLOWED_ASSETS), default="BTC")
    parser.add_argument(
        "--timeframe",
        choices=sorted(ALLOWED_TIMEFRAMES),
        default="1h",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("artifacts/dummy/market_observer"),
        help="artifact root read by the dashboard",
    )
    parser.add_argument("--bars", type=int, default=96)
    args = parser.parse_args()

    envelope = build_demo_observation(
        args.asset,
        args.timeframe,
        bar_count=args.bars,
    )
    destination = ContentAddressedArtifactStore(args.root).write_observation(envelope)
    print(f"Wrote synthetic demo artifact: {destination}")
    print("Boundary: synthetic display fixture; not market data or evidence; authority false.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
