"""Self-scout: Dummy's own systematic tendencies, Belichick-style.

Great football programs scout THEMSELVES as hard as any opponent: find the
tendencies an opponent could exploit and the habits that leak points. Dummy's
loss engine attributes losses to scopes; this report instead decomposes the
fused forecast's OWN biases, independent of P&L:

  * directional lean -- does the fused forecast systematically favor YES (or
    the home/favorite framing that YES usually encodes) beyond what outcomes
    justified?
  * price-band calibration -- favorite / mid / longshot buckets: predicted vs
    realized frequency (the favorite-longshot bias, on ourselves);
  * overconfidence -- distance-from-half scaling: when we say 70/30 are we
    only 60/40 right?
  * post-loss behavior -- Brier on days following a losing settled day vs
    after winning days (a tilt/chase detector for the pipeline itself).

Report-only. Findings feed the debias/recalibration layers through review,
never by mutating weights directly.
"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORT_PATH = Path("runtime/autonomy/self_scout.json")
MIN_ROWS = 60
_BANDS = (
    ("longshot", 0.0, 0.35),
    ("mid", 0.35, 0.65),
    ("favorite", 0.65, 1.001),
)
LEAN_WARN = 0.06          # mean(YES prob) - realized YES rate beyond this = lean
OVERCONFIDENCE_WARN = 0.85  # calibration slope below this = overconfident


def _rows(conn: sqlite3.Connection, days: float | None) -> list[tuple]:
    from autonomy.retention import install_signal_history

    install_signal_history(conn)
    clause = ""
    params: list[Any] = []
    if days is not None:
        clause = " AND s.created_at >= datetime('now', ?)"
        params.append(f"-{float(days)} day")
    return conn.execute(
        """
        SELECT s.market_ticker, s.probability_yes, s.created_at, t.result_yes
        FROM signal_history s
        JOIN settlements t ON t.market_ticker = s.market_ticker
        WHERE s.source = 'fused_forecast' AND s.mode = 'live'
        """ + clause + " ORDER BY s.created_at",
        params,
    ).fetchall()


def _band(probability: float) -> str:
    for name, low, high in _BANDS:
        if low <= probability < high:
            return name
    return "mid"


def build_self_scout(
    conn: sqlite3.Connection, *, days: float | None = 90.0,
) -> dict[str, Any]:
    rows = _rows(conn, days)
    n = len(rows)
    report: dict[str, Any] = {
        "report_version": "self_scout_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows": n,
        "purpose": (
            "decompose the fused forecast's own systematic tendencies "
            "(directional lean, band calibration, overconfidence, post-loss "
            "behavior) so exploitable habits are found before the market "
            "finds them; report-only"
        ),
    }
    if n < MIN_ROWS:
        report["status"] = "INSUFFICIENT_ROWS"
        return report

    # Directional lean: predicted YES mass vs realized YES rate.
    mean_prob = sum(float(p) for _t, p, _c, _r in rows) / n
    yes_rate = sum(1 for _t, _p, _c, r in rows if r) / n
    lean = mean_prob - yes_rate

    # Band calibration + overconfidence regression through (0.5, 0.5).
    bands: dict[str, dict[str, float]] = defaultdict(lambda: {"n": 0, "p": 0.0, "y": 0.0})
    num = den = 0.0
    for _ticker, prob, _created, result in rows:
        p = float(prob)
        y = 1.0 if result else 0.0
        cell = bands[_band(p)]
        cell["n"] += 1
        cell["p"] += p
        cell["y"] += y
        num += (p - 0.5) * (y - 0.5)
        den += (p - 0.5) ** 2
    slope = num / den if den > 0 else None

    # Post-loss behavior: daily Brier conditioned on the PREVIOUS settled
    # day's mean Brier being worse/better than the period median.
    daily: dict[str, list[float]] = defaultdict(list)
    for _ticker, prob, created, result in rows:
        day = str(created)[:10]
        outcome = 1.0 if result else 0.0
        daily[day].append((float(prob) - outcome) ** 2)
    day_means = {d: sum(v) / len(v) for d, v in daily.items() if v}
    ordered = sorted(day_means)
    after_bad: list[float] = []
    after_good: list[float] = []
    if len(ordered) >= 4:
        median = sorted(day_means.values())[len(day_means) // 2]
        for prev, cur in zip(ordered, ordered[1:]):
            (after_bad if day_means[prev] > median else after_good).append(day_means[cur])

    warnings: list[str] = []
    if abs(lean) > LEAN_WARN:
        warnings.append(
            "directional_lean_yes" if lean > 0 else "directional_lean_no"
        )
    if slope is not None and slope < OVERCONFIDENCE_WARN:
        warnings.append("overconfident_forecasts")
    tilt_delta = None
    if after_bad and after_good:
        tilt_delta = round(
            sum(after_bad) / len(after_bad) - sum(after_good) / len(after_good), 6,
        )
        if tilt_delta > 0.01:
            warnings.append("worse_after_bad_days_possible_regime_or_tilt")

    report.update({
        "status": "OK",
        "directional": {
            "mean_forecast_yes": round(mean_prob, 4),
            "realized_yes_rate": round(yes_rate, 4),
            "lean": round(lean, 4),
        },
        "band_calibration": {
            name: {
                "n": int(cell["n"]),
                "mean_forecast": round(cell["p"] / cell["n"], 4),
                "realized_rate": round(cell["y"] / cell["n"], 4),
                "gap": round(cell["p"] / cell["n"] - cell["y"] / cell["n"], 4),
            }
            for name, cell in sorted(bands.items())
            if cell["n"] >= 10
        },
        "overconfidence": {
            "calibration_slope": round(slope, 4) if slope is not None else None,
            "interpretation": "1.0 = perfectly scaled; <1 = overconfident",
        },
        "post_loss_behavior": {
            "days_after_bad": len(after_bad),
            "days_after_good": len(after_good),
            "brier_delta_after_bad_vs_good": tilt_delta,
        },
        "warnings": warnings,
        "self_scout_clean": not warnings,
    })
    return report


def write_self_scout(
    db_path: Path | str, *, path: Path | str = REPORT_PATH, days: float | None = 90.0,
) -> dict[str, Any]:
    conn = sqlite3.connect(f"file:{Path(db_path)}?mode=ro", uri=True)
    try:
        report = build_self_scout(conn, days=days)
    finally:
        conn.close()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(target)
    return report
