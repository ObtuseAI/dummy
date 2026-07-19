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
) -> dict[str, Any]:
    """The full per-scope block for the dashboard snapshot:

        {"CRYPTO": {"scopes": {"BTC": {summary, progression, picks}, ...},
                    "summary": {...aggregate...}},
         "SPORTS": {...}}
    """
    records = _settled_records(conn, window_days)
    rankings = _rankings(conn)

    verticals: dict[str, dict[str, Any]] = {}
    # Group settled records by (vertical, label).
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
        }

    # Vertical-level rollup across its scopes.
    for vertical, block in verticals.items():
        recs = [r for r in records if r["vertical"] == vertical]
        block["summary"] = _summarize(recs)
        block["open_picks"] = sum(len(s["picks"]) for s in block["scopes"].values())

    return {
        "window_days": window_days,
        "verticals": verticals,
    }


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
