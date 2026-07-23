"""Wave-51: per-scope (coin / league) analytics for the redesigned dashboard.

The dashboard's crypto and sports tabs break the organism's performance down by
the thing an operator actually thinks in -- a coin (BTC/ETH/SOL) or a league
(MLB/NFL/NBA/...). This module computes that breakdown from the ledger.

Truth first: the organism mostly ABSTAINS or is capital-gated (only a handful of
paper trades ever fill), so per-scope *trade* P&L is a tiny sample. The dense,
honest signal is **forecast accuracy** -- how well the model's probability graded
against settlement -- over tens of thousands of settled markets. So the per-scope
metrics lead with graded-forecast quality (Brier, hit-rate, edge vs the market's
own implied price), using the last pre-settlement fused forecast per market as
the pick of record. Older decision-only history is used only when no fused
forecast exists, so a market is never counted twice and post-settlement data is
never allowed to leak into the grade.

All reads run in the snapshot writer (which already holds the ledger), never on
the dashboard's request path -- the dashboard serves the persisted artifact and
never opens the ledger (the Wave-42 contention rule).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from autonomy.ontology import Vertical
from autonomy.scanner import classify_vertical
from autonomy.sports_markets import SPORTS_LEAGUES

# Crypto coin resolved by ticker prefix (longest/most-specific first).
_CRYPTO_COIN_PREFIXES: tuple[tuple[str, str], ...] = (
    ("KXBTC", "BTC"), ("BTCD", "BTC"), ("BTC", "BTC"),
    ("KXETH", "ETH"), ("ETHD", "ETH"), ("ETH", "ETH"),
    ("KXSOL", "SOL"), ("SOLD", "SOL"), ("SOLE", "SOL"), ("SOL", "SOL"),
)

# Scopes the dashboard surfaces as browsable tabs.
CRYPTO = "CRYPTO"
SPORTS = "SPORTS"

# The full league roster the SPORTS board always lists, in season or not
# (MLB + the team-sport specialist leagues; UFC/F1 retired). A league with no
# graded markets in the current window still appears -- flagged in/out of
# season, with last-season grades filled in from a widened lookback.
# Backwards-compatible public name used by the snapshot builder and tests.  The
# canonical roster lives next to the sports series registry.
SPORTS_ROSTER: tuple[str, ...] = SPORTS_LEAGUES
# How far back "last season" reaches for an out-of-season / dormant league.
# One scan at this window costs ~the same as the 120d one (the expensive
# per-market de-dup over decisions is window-independent), so the wider read
# is split in Python into a current slice + a last-season slice.
LAST_SEASON_WINDOW_DAYS = 400.0
_SEASON_STATE_PATH = Path("runtime/autonomy/season_state.json")


def load_season_active(path: Path | None = None) -> dict[str, bool]:
    """``{league_lower: active}`` from the SeasonMonitor state; {} on any miss.

    Fail-soft: a missing/corrupt file yields no verdicts, and the builder then
    treats every roster league as in-season (the monitor's own fail-open
    default) rather than silently marking leagues dormant.
    """
    try:
        raw = json.loads((path or _SEASON_STATE_PATH).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 -- absent/partial state must never raise
        return {}
    out: dict[str, bool] = {}
    for league, verdict in (raw or {}).items():
        if isinstance(verdict, dict) and "active" in verdict:
            out[str(league).lower()] = bool(verdict.get("active"))
    return out


def scope_key(ticker: str) -> tuple[str, str]:
    """(vertical, label) for a market ticker -- ('CRYPTO','BTC') / ('SPORTS','MLB').

    Crypto resolves to a coin, sports to a league; anything else is bucketed
    under its vertical name so nothing is silently dropped.
    """
    vertical = classify_vertical(ticker)
    upper = ticker.upper()
    if vertical is Vertical.CRYPTO:
        for prefix, coin in _CRYPTO_COIN_PREFIXES:
            if upper.startswith(prefix):
                return CRYPTO, coin
        return CRYPTO, "OTHER"
    if vertical is Vertical.SPORTS:
        from autonomy.picks import _scope_of

        league, _market_type = _scope_of(ticker)
        label = (league or "OTHER").upper()
        return SPORTS, ("OTHER" if label == "OTHER" or label == "" else label)
    return vertical.name, vertical.name


def bet_type_of(ticker: str) -> str:
    """The wager family a market belongs to, for per-bet-type accuracy slicing.

    Sports resolve to the registry's ``market_type`` (winner / spread / total /
    team_total / yrfi / prop / …); crypto to its contract family (ladder /
    between / 15m_direction / …); anything else to ``"other"``.
    """
    vertical = classify_vertical(ticker)
    if vertical is Vertical.CRYPTO:
        from autonomy.signals.crypto_spot import parse_crypto_ticker

        parsed = parse_crypto_ticker(ticker) or {}
        return str(parsed.get("contract_family") or "other")
    if vertical is Vertical.SPORTS:
        from autonomy.picks import _scope_of

        _league, market_type = _scope_of(ticker)
        return str(market_type or "other")
    return "other"


def _brier(prob: float, result: int) -> float:
    return (prob - result) ** 2


def _settled_records(conn: sqlite3.Connection, window_days: float) -> list[dict[str, Any]]:
    """Graded forecast-of-record per settled market inside the window.

    The record is our FUSED forecast (the ``fused_forecast`` signal), which is
    emitted for EVERY market we price -- traded or not. Grading that (phantom
    grading) is the honest per-scope accuracy: a league we forecast but never
    take an actionable side on (e.g. WNBA, priced but below the trade bar) still
    gets counted, instead of vanishing because it produced no BUY decision. The
    final *pre-settlement* fused emission per market is the pick of record (so a
    market re-priced every cycle counts once); the last pre-settlement decision
    marks which were actually traded. Ledgers from before fused emissions were
    introduced fall back to that decision as their forecast-of-record. A fused
    row always wins when both exist, and post-settlement rows are excluded to
    prevent look-ahead leakage. ``market_implied_yes`` rides in fused features
    JSON and is stored directly on a decision fallback.
    """
    rows = conn.execute(
        """
        WITH signal_candidates AS (
            SELECT sig.market_ticker AS ticker,
                   sig.probability_yes AS prob,
                   sig.features AS features,
                   s.result_yes AS result,
                   s.settled_at AS settled_at,
                   ROW_NUMBER() OVER (
                       PARTITION BY sig.market_ticker
                       ORDER BY datetime(sig.created_at) DESC, sig.rowid DESC
                   ) AS recency
            FROM signals sig
            JOIN settlements s ON s.market_ticker = sig.market_ticker
            WHERE sig.source = 'fused_forecast'
              AND datetime(sig.created_at) <= datetime(s.settled_at)
              AND datetime(s.settled_at) >= datetime('now', ?)
        ),
        decision_candidates AS (
            SELECT d.market_ticker AS ticker,
                   d.probability_yes AS prob,
                   d.market_implied_yes AS market,
                   d.action AS action,
                   s.result_yes AS result,
                   s.settled_at AS settled_at,
                   ROW_NUMBER() OVER (
                       PARTITION BY d.market_ticker
                       ORDER BY datetime(d.created_at) DESC, d.rowid DESC
                   ) AS recency
            FROM decisions d
            JOIN settlements s ON s.market_ticker = d.market_ticker
            WHERE datetime(d.created_at) <= datetime(s.settled_at)
              AND datetime(s.settled_at) >= datetime('now', ?)
        )
        SELECT sig.ticker, sig.prob, sig.features, sig.result, sig.settled_at,
               dec.action, NULL AS decision_market, 'fused_forecast' AS record_source
        FROM signal_candidates sig
        LEFT JOIN decision_candidates dec
          ON dec.ticker = sig.ticker AND dec.recency = 1
        WHERE sig.recency = 1

        UNION ALL

        SELECT dec.ticker, dec.prob, NULL AS features, dec.result, dec.settled_at,
               dec.action, dec.market AS decision_market, 'decision_fallback' AS record_source
        FROM decision_candidates dec
        WHERE dec.recency = 1
          AND NOT EXISTS (
              SELECT 1 FROM signal_candidates sig
              WHERE sig.ticker = dec.ticker AND sig.recency = 1
          )
        """,
        (f"-{float(window_days)} days", f"-{float(window_days)} days"),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for ticker, prob, features, result, settled_at, action, decision_market, record_source in rows:
        try:
            prob_f = float(prob)
            result_i = 1 if int(result) else 0
        except (TypeError, ValueError):
            continue
        market = None
        if features:
            try:
                mv = json.loads(features).get("market_implied_yes")
                market = float(mv) if mv is not None else None
            except (ValueError, TypeError, AttributeError):
                market = None
        elif decision_market is not None:
            try:
                market = float(decision_market)
            except (TypeError, ValueError):
                market = None
        vertical, label = scope_key(str(ticker))
        out.append({
            "ticker": str(ticker),
            "vertical": vertical,
            "label": label,
            "bet_type": bet_type_of(str(ticker)),
            "action": str(action) if action is not None else "",
            "prob": prob_f,
            "market": market,
            "ev_cents": 0.0,
            "result": result_i,
            "settled_at": str(settled_at),
            "record_source": str(record_source),
        })
    return out


def _summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Graded-forecast quality for one bundle of settled records."""
    n = len(records)
    if n == 0:
        return {"n": 0, "brier": None, "hit_rate": None,
                "market_brier": None, "brier_edge": None, "traded": 0}
    brier = sum(_brier(r["prob"], r["result"]) for r in records) / n
    hits = sum(1 for r in records if (r["prob"] >= 0.5) == (r["result"] == 1))
    contested = [r for r in records if r["market"] is not None]
    market_brier = (
        sum(_brier(r["market"], r["result"]) for r in contested) / len(contested)
        if contested else None
    )
    # Edge = how much better the model's Brier is than the market's own price
    # (positive => the model beat the line). Only meaningful on contested rows.
    model_brier_contested = (
        sum(_brier(r["prob"], r["result"]) for r in contested) / len(contested)
        if contested else None
    )
    brier_edge = (
        market_brier - model_brier_contested
        if market_brier is not None and model_brier_contested is not None else None
    )
    traded = sum(1 for r in records if r["action"] in ("BUY_YES", "BUY_NO"))
    return {
        "n": n,
        "brier": round(brier, 4),
        "hit_rate": round(hits / n, 4),
        "market_brier": round(market_brier, 4) if market_brier is not None else None,
        "brier_edge": round(brier_edge, 4) if brier_edge is not None else None,
        "contested_n": len(contested),
        "traded": traded,
    }


def _progression(records: list[dict[str, Any]], buckets: int = 24) -> list[dict[str, Any]]:
    """Accuracy over time: settled records split into equal-count time buckets,
    oldest first, each carrying its Brier and hit-rate. Equal-count (not
    equal-width) keeps every point statistically comparable."""
    ordered = sorted(records, key=lambda r: r["settled_at"])
    n = len(ordered)
    if n < 4:
        return []
    size = max(1, n // min(buckets, n))
    out: list[dict[str, Any]] = []
    for start in range(0, n, size):
        chunk = ordered[start:start + size]
        if not chunk:
            continue
        s = _summarize(chunk)
        out.append({
            "t": chunk[-1]["settled_at"],
            "n": s["n"],
            "brier": s["brier"],
            "hit_rate": s["hit_rate"],
            "brier_edge": s["brier_edge"],
        })
    return out


_IMPROVE_MIN_HALF = 30         # min records per half before a trend is honest
_IMPROVE_BRIER_EPS = 0.005     # Brier move smaller than this reads as flat


def _improvement(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Is this bundle getting SHARPER? Split oldest->newest in half and compare.

    ``delta_brier = prior_brier - recent_brier`` (positive => Brier fell =>
    sharper). Below a per-half floor the sample is too thin to call, so the
    trend is reported as ``"thin"`` rather than a spurious direction.
    """
    ordered = sorted(records, key=lambda r: r["settled_at"])
    n = len(ordered)
    if n < 2 * _IMPROVE_MIN_HALF:
        return {"trend": "thin", "n": n, "delta_brier": None,
                "delta_hit": None, "delta_edge": None}
    half = n // 2
    prior, recent = _summarize(ordered[:half]), _summarize(ordered[half:])

    def _delta(a: Any, b: Any) -> float | None:
        return None if a is None or b is None else round(b - a, 4)

    delta_brier = _delta(recent["brier"], prior["brier"])   # prior - recent
    delta_hit = _delta(prior["hit_rate"], recent["hit_rate"])
    delta_edge = _delta(prior["brier_edge"], recent["brier_edge"])
    trend = "flat"
    if delta_brier is not None:
        if delta_brier > _IMPROVE_BRIER_EPS:
            trend = "improving"
        elif delta_brier < -_IMPROVE_BRIER_EPS:
            trend = "declining"
    return {
        "trend": trend, "n": n, "recent_n": n - half, "prior_n": half,
        "delta_brier": delta_brier, "delta_hit": delta_hit, "delta_edge": delta_edge,
        "recent_brier": recent["brier"], "prior_brier": prior["brier"],
    }


def _bet_type_breakdown(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per-bet-type accuracy + improvement for one scope's settled records."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for rec in records:
        groups.setdefault(rec.get("bet_type", "other"), []).append(rec)
    return {
        bt: {"summary": _summarize(recs), "improvement": _improvement(recs)}
        for bt, recs in sorted(groups.items(), key=lambda kv: -len(kv[1]))
    }


def _pick_board(picks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Open picks grouped by bet type, each list ranked by edge (picks arrive
    edge-sorted per scope) -- the per-bet-type rankings the operator drills into."""
    board: dict[str, list[dict[str, Any]]] = {}
    for pick in picks:
        board.setdefault(pick.get("bet_type", "other"), []).append(pick)
    return board


def _settled_today(records: list[dict[str, Any]], cutoff: str) -> list[dict[str, Any]]:
    """Markets settled since ``cutoff`` (recent day), each with whether the
    model's directional call was correct -- the day's scoreboard."""
    from autonomy.market_labels import humanize_market

    out: list[dict[str, Any]] = []
    for rec in records:
        if rec.get("settled_at", "") < cutoff:
            continue
        prob, result = rec["prob"], rec["result"]
        hl = humanize_market(rec["ticker"])
        out.append({
            "ticker": rec["ticker"], "bet_type": rec.get("bet_type", "other"),
            "label": hl["label"], "matchup": hl["matchup"],
            "prob": round(prob, 3), "market": (round(rec["market"], 3) if rec["market"] is not None else None),
            "result": result, "correct": (prob >= 0.5) == (result == 1),
            "lean": "YES" if prob >= 0.5 else "NO",
            "traded": rec["action"] in ("BUY_YES", "BUY_NO"),
            "settled_at": rec["settled_at"],
        })
    return sorted(out, key=lambda x: x["settled_at"], reverse=True)


def _rankings(conn: sqlite3.Connection, limit: int = 12) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Current best actionable picks per scope: the latest decision on each
    still-unsettled market where the model took a side, ranked by edge (EV)."""
    rows = conn.execute(
        """
        SELECT d.market_ticker AS ticker, d.action AS action, d.side AS side,
               d.probability_yes AS prob, d.market_implied_yes AS market,
               d.ev_cents AS ev_cents, d.price_cents AS price_cents, d.created_at AS created_at
        FROM decisions d
        JOIN (
            SELECT market_ticker, MAX(created_at) AS mx
            FROM decisions GROUP BY market_ticker
        ) last ON last.market_ticker = d.market_ticker AND last.mx = d.created_at
        LEFT JOIN settlements s ON s.market_ticker = d.market_ticker
        WHERE s.market_ticker IS NULL
          AND d.action IN ('BUY_YES', 'BUY_NO')
        """
    ).fetchall()
    from autonomy.market_labels import humanize_market, recommend_side

    by_scope: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for ticker, action, side, prob, market, ev_cents, price_cents, created_at in rows:
        key = scope_key(str(ticker))
        hl = humanize_market(str(ticker))
        by_scope.setdefault(key, []).append({
            "ticker": str(ticker),
            "label": hl["label"],
            "matchup": hl["matchup"],
            "game_date": hl["date"],
            "side": str(side),
            # Plain, unmistakable recommended action (incl. YRFI YES/NO).
            "recommendation": recommend_side(str(ticker), str(side)),
            "bet_type": bet_type_of(str(ticker)),
            "prob": round(float(prob), 3) if prob is not None else None,
            "market": round(float(market), 3) if market is not None else None,
            "edge_cents": round(float(ev_cents), 1) if ev_cents is not None else 0.0,
            "price_cents": int(price_cents) if price_cents is not None else None,
            "created_at": str(created_at),
        })
    for key, picks in by_scope.items():
        picks.sort(key=lambda p: p["edge_cents"], reverse=True)
        by_scope[key] = picks[:limit]
    return by_scope


def build_scope_analytics(
    conn: sqlite3.Connection,
    *,
    window_days: float = 120.0,
    season_active: dict[str, bool] | None = None,
    last_season_window_days: float = LAST_SEASON_WINDOW_DAYS,
) -> dict[str, Any]:
    """The full per-scope block for the dashboard snapshot:

        {"CRYPTO": {"scopes": {"BTC": {summary, progression, picks}, ...},
                    "summary": {...aggregate...}},
         "SPORTS": {...}}

    ``season_active`` maps ``league_lower -> is_active`` (from
    :func:`load_season_active`). Every league in :data:`SPORTS_ROSTER` is
    listed regardless of activity: an out-of-season or as-yet-ungraded league
    still gets a scope, flagged ``in_season`` and back-filled from last season
    (a widened lookback) so the operator sees the whole slate, not just what
    happens to have settled this window.
    """
    season_active = {str(k).lower(): bool(v) for k, v in (season_active or {}).items()}

    # One wide scan; the trailing ``window_days`` slice is the current season.
    # (De-duping the pick-of-record per market scans all decisions either way,
    # so a 400d read costs ~the same as 120d -- we just split it in Python.)
    wide = _settled_records(conn, max(window_days, last_season_window_days))
    cutoff = conn.execute(
        "SELECT datetime('now', ?)", (f"-{float(window_days)} days",)
    ).fetchone()[0]
    today_cutoff = conn.execute("SELECT datetime('now', '-30 hours')").fetchone()[0]
    active_verticals = {CRYPTO, SPORTS}
    wide = [r for r in wide if r.get("vertical") in active_verticals]
    records = [r for r in wide if r["settled_at"] >= cutoff]
    rankings = {
        key: value for key, value in _rankings(conn).items()
        if key[0] in active_verticals
    }

    verticals: dict[str, dict[str, Any]] = {}
    # Group current-window settled records by (vertical, label).
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for rec in records:
        by_key.setdefault((rec["vertical"], rec["label"]), []).append(rec)

    # Union of scopes seen in settled history OR in current rankings.
    all_keys = set(by_key) | set(rankings)
    for vertical, label in sorted(all_keys):
        recs = by_key.get((vertical, label), [])
        block = verticals.setdefault(vertical, {"scopes": {}, "summary": {}})
        scope_picks = rankings.get((vertical, label), [])
        block["scopes"][label] = {
            "label": label,
            "summary": _summarize(recs),
            "progression": _progression(recs),
            "picks": scope_picks,
            "bet_types": _bet_type_breakdown(recs),
            "improvement": _improvement(recs),
            "pick_board": _pick_board(scope_picks),
            "settled_today": _settled_today(recs, today_cutoff),
        }

    # Always surface the whole SPORTS roster -- in or out of season.
    sports = verticals.setdefault(SPORTS, {"scopes": {}, "summary": {}})
    last_season: dict[str, list[dict[str, Any]]] = {}
    for rec in wide:
        if rec["vertical"] == SPORTS:
            last_season.setdefault(rec["label"], []).append(rec)
    for league in SPORTS_ROSTER:
        active = season_active.get(league.lower())
        in_season = True if active is None else active
        scope = sports["scopes"].get(league)
        current_grades = by_key.get((SPORTS, league), [])
        if scope is None or not current_grades:
            # An open forecast can create a scope without a single current
            # grade.  That is not proof the season is underway: preserve the
            # current picks, but source diagnostics from the last-season
            # window and label the basis honestly.
            ls = last_season.get(league, [])
            league_picks = rankings.get((SPORTS, league), [])
            scope = {
                "label": league,
                "summary": _summarize(ls),
                "progression": _progression(ls),
                "picks": league_picks,
                "bet_types": _bet_type_breakdown(ls),
                "improvement": _improvement(ls),
                "pick_board": _pick_board(league_picks),
                "settled_today": _settled_today(ls, today_cutoff),
                "basis": "last-season" if ls else "none",
            }
            sports["scopes"][league] = scope
        else:
            scope["basis"] = "current"
        scope["in_season"] = in_season
        # Three-state, so the badge never says "in season, awaiting grades":
        #   off      -> the season monitor sees no games in its window
        #   in       -> active AND we're grading current games (basis=current)
        #   upcoming -> active but no current grades yet (preseason on the
        #               scoreboard, or the slate hasn't tipped off) -- e.g. NFL
        #               in July, awake for its exhibition game but not "in season"
        if not in_season:
            scope["season_status"] = "off"
        elif scope.get("basis") == "current":
            scope["season_status"] = "in"
        else:
            scope["season_status"] = "upcoming"

    # Vertical-level rollup across its scopes (current window only).
    for vertical, block in verticals.items():
        recs = [r for r in records if r["vertical"] == vertical]
        block["summary"] = _summarize(recs)
        block["open_picks"] = sum(len(s["picks"]) for s in block["scopes"].values())

    return {
        "window_days": window_days,
        "last_season_window_days": last_season_window_days,
        "verticals": verticals,
        "telemetry": _telemetry(records, verticals),
    }


def _telemetry(
    records: list[dict[str, Any]], verticals: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Overall accuracy + improvement, and a scope x bet-type matrix.

    The overview reads ``overall`` for the headline + improvement arrow and
    ``matrix`` for the heatmap (one row per non-empty scope/bet-type cell).

    Scoped to what the organism still trades (crypto + sports); retired
    verticals' historical grades stay out of the "current organism" headline.
    """
    active = {CRYPTO, SPORTS}
    scoped = [r for r in records if r.get("vertical") in active]
    matrix: list[dict[str, Any]] = []
    for vertical, block in verticals.items():
        if vertical not in active:
            continue
        for label, scope in (block.get("scopes") or {}).items():
            for bet_type, cell in (scope.get("bet_types") or {}).items():
                s = cell.get("summary") or {}
                if not s.get("n"):
                    continue
                imp = cell.get("improvement") or {}
                matrix.append({
                    "vertical": vertical, "scope": label, "bet_type": bet_type,
                    "n": s.get("n"), "brier": s.get("brier"), "hit_rate": s.get("hit_rate"),
                    "brier_edge": s.get("brier_edge"), "contested_n": s.get("contested_n"),
                    "trend": imp.get("trend"), "delta_brier": imp.get("delta_brier"),
                })
    matrix.sort(key=lambda c: (c["vertical"], c["scope"], -(c["n"] or 0)))
    return {
        "overall": {"summary": _summarize(scoped), "improvement": _improvement(scoped)},
        "matrix": matrix,
    }


# ---- long-horizon accuracy history (improvement across model versions) ------
# The windowed improvement above lives inside the current settled window; this
# sidecar records the organism's overall accuracy at each snapshot so the
# dashboard can chart "are we getting sharper" over weeks -- across retunes and
# even after old settlements age out of the ledger's retention.
ACCURACY_HISTORY_PATH = Path("runtime/autonomy/accuracy_history.jsonl")
_ACCURACY_HISTORY_MAX = 5000


def _bound_jsonl(path: Path, max_lines: int) -> None:
    """Tail-preserve a jsonl file at ``max_lines`` (atomic tmp+replace)."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:  # noqa: BLE001
        return
    if len(lines) <= max_lines:
        return
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("\n".join(lines[-max_lines:]) + "\n", encoding="utf-8")
    tmp.replace(path)


def append_accuracy_history(
    telemetry: dict[str, Any], ts: str, *, path: Path | None = None,
    weights_hash: str | None = None,
) -> dict[str, Any] | None:
    """Append one overall-accuracy point. No-op (returns None) when nothing is
    graded yet, so the series never carries empty rows. Self-bounding."""
    target = Path(path) if path else ACCURACY_HISTORY_PATH
    overall = ((telemetry or {}).get("overall") or {}).get("summary") or {}
    if not overall.get("n"):
        return None
    row = {
        "ts": str(ts), "n": overall.get("n"), "brier": overall.get("brier"),
        "hit_rate": overall.get("hit_rate"), "brier_edge": overall.get("brier_edge"),
    }
    if weights_hash:
        row["weights"] = str(weights_hash)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    _bound_jsonl(target, _ACCURACY_HISTORY_MAX)
    return row


def read_accuracy_series(path: Path | None = None, limit: int = 180) -> list[dict[str, Any]]:
    """The last ``limit`` accuracy points, oldest->newest; [] on any miss."""
    target = Path(path) if path else ACCURACY_HISTORY_PATH
    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except Exception:  # noqa: BLE001
        return []
    out: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except Exception:  # noqa: BLE001
            continue
    return out


def _downsample(rows: list[Any], target: int = 140) -> list[Any]:
    """Even-stride downsample that always keeps the final point."""
    n = len(rows)
    if n <= target:
        return rows
    step = n / target
    picked = [rows[int(i * step)] for i in range(target)]
    if picked[-1] is not rows[-1]:
        picked.append(rows[-1])
    return picked


def build_overview(conn: sqlite3.Connection, report: dict[str, Any] | None) -> dict[str, Any]:
    """Build the primary overview without paper-result authority.

    The raw shadow ledger and historical backtest remain untouched for audit,
    but paper bankroll, P&L, and paper-result promotions are intentionally not
    copied into the operator overview.  A cached Kalshi live-account block is
    attached later at the artifact-only HTTP boundary.
    """
    _ = conn  # Signature retained for snapshot-builder compatibility.
    report = report or {}

    derived_weights = report.get("derived_weights") or {}
    active_sources = sorted(
        ({"source": s, "weight": round(float(w), 3)} for s, w in derived_weights.items()),
        key=lambda x: x["weight"], reverse=True,
    )

    return {
        "overview_schema_version": 2,
        "primary_account": "live_kalshi",
        "paper_results_status": "RETIRED_NON_AUTHORITATIVE",
        "paper_results_can_enable_live": False,
        "paper_results_can_block_live": False,
        "paper_history_preserved_for_audit": True,
        "live_authority_source": "explicit_live_control_contracts_only",
        "active_sources": active_sources[:12],
    }


def _load_artifact(runtime_dir: Path, name: str) -> Any:
    try:
        return json.loads((runtime_dir / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _specialist_for(vertical: str, label: str) -> str:
    # Crypto is one specialist shared across coins; sports is one per league.
    return "crypto" if vertical == CRYPTO else label.lower()


_MISPRICING_FIELDS = ("ticker", "side", "edge", "model_prob", "book_prob",
                      "market_prob", "confidence", "agreement", "rationale")


def build_scope_extras(
    runtime_dir: Path,
    scope_keys: list[tuple[str, str]],
    council_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """The legacy per-scope surfaces folded into 'other data', for the scopes the
    snapshot already knows about. Read fresh from the runtime artifacts (no
    ledger), so the live mispricing tape / council / ejections stay current
    between snapshots.

    Per scope: its specialist's council row (status, in-season, contested Brier,
    CLV, where-we-bleed), CLV-per-market-type, the live mispricing opportunities
    on that coin/league, and any ejection/injury events riding those markets.

    ``council_rows`` are the rich rows the caller already computes with the
    dashboard's ``_council_panel`` (kept there to avoid a circular import); when
    absent we fall back to the raw council snapshot's thinner per-specialist row.
    """
    if council_rows is not None:
        council_by_specialist = {
            str(r.get("name")): r for r in council_rows if r.get("name")
        }
    else:
        council_by_specialist = {
            str(s.get("name")): s
            for s in (_load_artifact(runtime_dir, "council_snapshot.json").get("specialists") or [])
            if isinstance(s, dict) and s.get("name")
        }

    clv_by_specialist: dict[str, list[dict[str, Any]]] = {}
    for key, scope in (_load_artifact(runtime_dir, "clv_report.json").get("scopes") or {}).items():
        if not isinstance(scope, dict):
            continue
        spec = str(scope.get("specialist") or str(key).split("|", 1)[0])
        clv_by_specialist.setdefault(spec, []).append({
            "market_type": scope.get("market_type") or str(key).split("|", 1)[-1],
            "clv_bps_mean": scope.get("clv_bps_mean"),
            "ci95_lower": scope.get("clv_bps_ci95_lower"),
            "ci95_upper": scope.get("clv_bps_ci95_upper"),
            "n_entries": scope.get("n_entries"),
        })

    from autonomy.market_labels import humanize_market

    misp_by_scope: dict[tuple[str, str], list[dict[str, Any]]] = {}
    ejections_by_scope: dict[tuple[str, str], list[Any]] = {}
    for row in (_load_artifact(runtime_dir, "mispricing_monitor_latest.json").get("shortlist") or []):
        if not isinstance(row, dict) or not row.get("ticker"):
            continue
        key = scope_key(str(row["ticker"]))
        enriched = {f: row.get(f) for f in _MISPRICING_FIELDS}
        enriched["label"] = humanize_market(str(row["ticker"]))["label"]
        misp_by_scope.setdefault(key, []).append(enriched)
        for ev in (row.get("ejection_events") or []):
            ejections_by_scope.setdefault(key, []).append(ev)
    for rows in misp_by_scope.values():
        rows.sort(key=lambda r: abs(r.get("edge") or 0), reverse=True)

    out: dict[str, Any] = {}
    for vertical, label in scope_keys:
        spec = _specialist_for(vertical, label)
        rows = misp_by_scope.get((vertical, label), [])
        out.setdefault(vertical, {})[label] = {
            "council": council_by_specialist.get(spec),
            "clv": clv_by_specialist.get(spec, []),
            "mispricing": rows[:10],
            "ejections": ejections_by_scope.get((vertical, label), [])[:10],
        }
    return out
