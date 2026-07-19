"""Wave-51: per-scope (coin / league) analytics for the redesigned dashboard.

The dashboard's crypto and sports tabs break the organism's performance down by
the thing an operator actually thinks in -- a coin (BTC/ETH/SOL) or a league
(MLB/NFL/NBA/...). This module computes that breakdown from the ledger.

Truth first: the organism mostly ABSTAINS or is capital-gated (only a handful of
paper trades ever fill), so per-scope *trade* P&L is a tiny sample. The dense,
honest signal is **forecast accuracy** -- how well the model's probability graded
against settlement -- over tens of thousands of settled markets. So the per-scope
metrics lead with graded-forecast quality (Brier, hit-rate, edge vs the market's
own implied price), using the LAST decision per settled market as the pick of
record (never counting a market's intra-cycle re-pricings more than once).

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
SPORTS_ROSTER: tuple[str, ...] = ("MLB", "WNBA", "NBA", "NFL", "NHL", "NCAAF", "NCAAMB")
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
    """Last decision per settled market inside the window, with its graded result.

    One row per market (the pick of record), so a market re-priced every cycle
    counts once -- honest accuracy, not inflated by re-emissions.
    """
    rows = conn.execute(
        """
        SELECT d.market_ticker  AS ticker,
               d.action         AS action,
               d.probability_yes AS prob,
               d.market_implied_yes AS market,
               d.ev_cents       AS ev_cents,
               s.result_yes     AS result,
               s.settled_at     AS settled_at
        FROM decisions d
        JOIN settlements s ON s.market_ticker = d.market_ticker
        JOIN (
            SELECT market_ticker, MAX(created_at) AS mx
            FROM decisions GROUP BY market_ticker
        ) last ON last.market_ticker = d.market_ticker AND last.mx = d.created_at
        WHERE s.settled_at >= datetime('now', ?)
        """,
        (f"-{float(window_days)} days",),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for ticker, action, prob, market, ev_cents, result, settled_at in rows:
        try:
            prob_f = float(prob)
            result_i = 1 if int(result) else 0
        except (TypeError, ValueError):
            continue
        vertical, label = scope_key(str(ticker))
        out.append({
            "ticker": str(ticker),
            "vertical": vertical,
            "label": label,
            "bet_type": bet_type_of(str(ticker)),
            "action": str(action),
            "prob": prob_f,
            "market": float(market) if market is not None else None,
            "ev_cents": float(ev_cents) if ev_cents is not None else 0.0,
            "result": result_i,
            "settled_at": str(settled_at),
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


_IMPROVE_MIN_HALF = 4          # min records per half before a trend is honest
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
    by_scope: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for ticker, action, side, prob, market, ev_cents, price_cents, created_at in rows:
        key = scope_key(str(ticker))
        by_scope.setdefault(key, []).append({
            "ticker": str(ticker),
            "side": str(side),
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
    records = [r for r in wide if r["settled_at"] >= cutoff]
    rankings = _rankings(conn)

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
        block["scopes"][label] = {
            "label": label,
            "summary": _summarize(recs),
            "progression": _progression(recs),
            "picks": rankings.get((vertical, label), []),
            "bet_types": _bet_type_breakdown(recs),
            "improvement": _improvement(recs),
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
        if scope is None:
            # No current-window grade -> fall back to last season's slate.
            ls = last_season.get(league, [])
            scope = {
                "label": league,
                "summary": _summarize(ls),
                "progression": _progression(ls),
                "picks": rankings.get((SPORTS, league), []),
                "bet_types": _bet_type_breakdown(ls),
                "improvement": _improvement(ls),
                "basis": "last-season" if ls else "none",
            }
            sports["scopes"][league] = scope
        else:
            scope["basis"] = "current"
        scope["in_season"] = in_season

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
    """
    matrix: list[dict[str, Any]] = []
    for vertical, block in verticals.items():
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
        "overall": {"summary": _summarize(records), "improvement": _improvement(records)},
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
    """The overview block: the paper account, its balance curve, realized paper
    P&L / ROI, the actively-promoted challengers, and the ones closest to
    promotion. The account is the shadow PAPER bankroll -- live capital is
    human-gated -- and is labelled as such so nothing implies real money.
    """
    report = report or {}
    curve_rows = conn.execute(
        "SELECT bankroll_cents, open_exposure_cents, stage, created_at "
        "FROM bankroll_curve ORDER BY id"
    ).fetchall()
    balance_curve = [
        {"t": str(created_at), "bankroll_cents": int(bankroll), "exposure_cents": int(exposure)}
        for bankroll, exposure, _stage, created_at in curve_rows
    ]
    base = int(curve_rows[0][0]) if curve_rows else 10_000   # first recorded bankroll
    latest = curve_rows[-1] if curve_rows else None
    bankroll = int(latest[0]) if latest else base
    exposure = int(latest[1]) if latest else 0
    stage = int(latest[2]) if latest else 0
    account_roi = (bankroll - base) / base if base else 0.0

    rts = report.get("realized_trade_statistics") or {}
    gates = report.get("crypto_challenger_gates") or {}
    promoted: list[dict[str, Any]] = []
    close: list[dict[str, Any]] = []
    for name, gate in gates.items():
        if not isinstance(gate, dict):
            continue
        evidence = gate.get("evidence") or {}
        lower95 = evidence.get("contested_brier_advantage_lower95")
        entry = {
            "name": name,
            "lower95": lower95,
            "contested_markets": evidence.get("contested_markets"),
            "settled_markets": evidence.get("settled_markets"),
            "blocker": (gate.get("blockers") or [None])[0],
            "auto_promote": bool(gate.get("auto_promote")),
            "execution_authority": bool(gate.get("execution_authority")),
            "ready": bool(gate.get("ready_for_explicit_fusion_review")),
        }
        if entry["auto_promote"] or entry["execution_authority"] or entry["ready"]:
            promoted.append(entry)
        elif lower95 is not None:
            close.append(entry)
    # Closest to promotion first: the least-negative contested-Brier lower bound
    # (nearest to clearing the > 0 threshold).
    close.sort(key=lambda e: e["lower95"] if e["lower95"] is not None else -9.0, reverse=True)

    derived_weights = report.get("derived_weights") or {}
    active_sources = sorted(
        ({"source": s, "weight": round(float(w), 3)} for s, w in derived_weights.items()),
        key=lambda x: x["weight"], reverse=True,
    )

    return {
        "paper": True,
        "bankroll_cents": bankroll,
        "base_bankroll_cents": base,
        "exposure_cents": exposure,
        "stage": stage,
        "account_roi": round(account_roi, 4),
        "realized_pnl_cents": report.get("realized_decision_pnl_cents"),
        "realized_trade_statistics": {
            k: rts.get(k) for k in (
                "net_pnl_cents", "roi_on_entry_cost", "win_rate",
                "trades", "profit_factor", "max_drawdown_cents",
            )
        },
        "balance_curve": _downsample(balance_curve),
        "promoted": promoted,
        "close_to_promotion": close[:8],
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

    misp_by_scope: dict[tuple[str, str], list[dict[str, Any]]] = {}
    ejections_by_scope: dict[tuple[str, str], list[Any]] = {}
    for row in (_load_artifact(runtime_dir, "mispricing_monitor_latest.json").get("shortlist") or []):
        if not isinstance(row, dict) or not row.get("ticker"):
            continue
        key = scope_key(str(row["ticker"]))
        misp_by_scope.setdefault(key, []).append({f: row.get(f) for f in _MISPRICING_FIELDS})
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
