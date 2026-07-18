"""Ignition for the vNext sovereign-forecasting shadow runtime (Wave-26).

The 8-phase vNext stack (``dummy/organisms`` and friends) was built and
tested 2026-07-14 but never RAN: nothing scheduled it, so its empirical
gates stayed open and every claim read "insufficient evidence". This module
is the bridge that turns it over -- shadow-only, exactly as its constitution
demands:

  ISSUE     candidate markets come from the live bet-board artifact (the
            brain already captured point-in-time quotes + the fused
            incumbent view there each cycle -- zero new network reads).
            Each becomes an organism episode: frozen evidence, six agents,
            competing futures, a synthesis decision, simulated (never real)
            execution. Issued artifacts wait in a pending file.
  COMPLETE  when the autonomy ledger records the market's settlement, the
            issued episode is completed against verified truth: agents are
            graded, trust proposals derived, memory archived, replay
            verified. Held-out replay cases are REAL settled fused rows
            from the same ledger, not fixtures.
  STATUS    every pass writes ``vnext_shadow_status.json`` for the
            dashboard and the improvement planner.

No authority changes anywhere: episodes simulate execution, promotion
review remains human-only, and the incumbent stack keeps flying the plane.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

RUNTIME_DIR = Path("runtime/autonomy")
PENDING_PATH = RUNTIME_DIR / "vnext_pending.jsonl"
EPISODES_PATH = RUNTIME_DIR / "vnext_episodes.jsonl"
STATUS_PATH = RUNTIME_DIR / "vnext_shadow_status.json"

POLICY_VERSION = "wave26-ignition-v1"
MAX_ISSUES_PER_PASS = 8
PENDING_EXPIRY_HOURS = 48.0
HELD_OUT_COUNT = 5

# Phase 3 shipped exactly TWO organism templates, each with a strict
# (ticker prefix, market_type, vertical, clock, incumbent family) contract.
# The ignition surface honors that: BTC 15m directions (fast settlements
# feed the empirical gates quickest) and MLB pregame winners. More shapes
# join by ADDING TEMPLATES in dummy/organisms/templates.py, not by loosening
# this table.
_TEMPLATE_SHAPES: tuple[dict[str, str], ...] = (
    {
        "ticker_prefix": "KXBTC15M",
        "market_type": "15m_direction",
        "vertical": "crypto",
        "clock_domain": "fifteen_minute",
        "incumbent_family": "crypto-coinbase-distribution",
    },
    {
        "ticker_prefix": "KXMLBGAME",
        "market_type": "winner",
        "vertical": "mlb",
        "clock_domain": "pregame",
        "incumbent_family": "mlb-structural",
    },
)


def _shape_for(ticker: str) -> dict[str, str] | None:
    upper = str(ticker).upper()
    for shape in _TEMPLATE_SHAPES:
        if upper.startswith(shape["ticker_prefix"]):
            return shape
    return None


def _utc(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)




def eligible_rows(board: dict[str, Any], pending_ids: set[str]) -> list[dict[str, Any]]:
    """Board rows the runtime can issue against: coherent open book, fused
    incumbent view, a real close time, not already pending."""
    out: list[dict[str, Any]] = []
    for league_groups in (board.get("groups") or {}).values():
        for rows in league_groups.values():
            for row in rows:
                if row.get("ticker") in pending_ids:
                    continue
                quotes = [row.get(k) for k in ("yes_bid", "yes_ask", "no_bid", "no_ask")]
                if any(q is None for q in quotes):
                    continue
                yes_bid, yes_ask, no_bid, no_ask = (int(q) for q in quotes)
                if not (1 <= yes_bid <= yes_ask <= 99 and 1 <= no_bid <= no_ask <= 99
                        and yes_ask + no_bid == 100 and no_ask + yes_bid == 100):
                    continue
                if row.get("market_probability") is None or row.get("close_time") is None:
                    continue
                if _shape_for(str(row.get("ticker"))) is None:
                    continue
                close = _utc(row["close_time"])
                if close is None or close <= datetime.now(timezone.utc):
                    continue
                out.append(row)
    # Fast-settling markets first: crypto expiries feed the gates quickest.
    out.sort(key=lambda r: str(r.get("close_time")))
    return out


def build_issue_request(row: dict[str, Any], generated_at: str):
    from dummy.organisms.models import (
        AgentVertical,
        ClockDomain,
        IssueRequest,
        PointInTimeEvidence,
    )

    ticker = str(row["ticker"])
    shape = _shape_for(ticker)
    if shape is None:
        raise ValueError(f"no organism template shape for {ticker}")
    now = datetime.now(timezone.utc)
    observed = _utc(generated_at) or now
    close = _utc(row["close_time"])
    depth = max(1, int(row.get("liquidity") or 1))
    evidence = (
        PointInTimeEvidence(
            evidence_id=f"quote-{ticker}",
            source_family="kalshi-public-quote",
            observed_at=observed,
            received_at=now,
            source_reference=f"artifact://bet_board/{ticker}",
            observed_at_verified=True,
            received_at_verified=True,
            payload={
                "kind": "market_quote",
                "market_id": ticker,
                "status": "open",
                "yes_bid": int(row["yes_bid"]),
                "yes_ask": int(row["yes_ask"]),
                "no_bid": int(row["no_bid"]),
                "no_ask": int(row["no_ask"]),
                "yes_ask_depth": depth,
                "no_ask_depth": depth,
            },
            limitations=("depth proxied from listed liquidity, not book levels",),
        ),
        PointInTimeEvidence(
            evidence_id=f"incumbent-{ticker}",
            source_family="incumbent-fused",
            observed_at=observed,
            received_at=now,
            source_reference=f"artifact://bet_board/{ticker}#fused",
            observed_at_verified=True,
            received_at_verified=True,
            payload={
                "kind": "incumbent_forecast",
                "market_id": ticker,
                "probability_yes": float(row["probability"]),
                "uncertainty": float(row.get("uncertainty") or 0.25),
                "source_family": shape["incumbent_family"],
                "source": "fused_forecast",
                "model_version": "fused_forecast-live",
                "calibration_identity": "reliability-maps-validated",
                "features": {"edge": row.get("edge")},
                "assumptions": ["board_artifact_is_point_in_time"],
                "failure_conditions": ["stale_board_cycle"],
            },
        ),
    )
    return IssueRequest(
        market_id=ticker,
        market_type=shape["market_type"],
        vertical=AgentVertical(shape["vertical"]),
        clock_domain=ClockDomain(shape["clock_domain"]),
        objective="shadow forecast vs incumbent and market prior",
        policy_version=POLICY_VERSION,
        decision_at=now,
        market_close_at=close,
        event_cluster_id=ticker.rsplit("-", 1)[0],
        evidence=evidence,
        max_shadow_contracts=1,
    )


def load_pending() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        with PENDING_PATH.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    records.append(json.loads(line))
                except (ValueError, TypeError):
                    continue
    except OSError:
        pass
    return records


def save_pending(records: list[dict[str, Any]]) -> None:
    PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = PENDING_PATH.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, sort_keys=True, default=str) + "\n")
    temporary.replace(PENDING_PATH)


def held_out_cases_from_ledger(conn: sqlite3.Connection):
    """Real, already-settled fused rows as held-out replay cases."""
    from autonomy.retention import install_signal_history
    from dummy.organisms.models import HeldOutCase

    install_signal_history(conn)
    rows = conn.execute(
        """
        SELECT s.market_ticker, s.probability_yes, s.features, st.result_yes
        FROM signal_history s
        JOIN settlements st ON st.market_ticker = s.market_ticker
        WHERE s.source = 'fused_forecast'
        ORDER BY s.created_at DESC LIMIT 40
        """
    ).fetchall()
    cases = []
    seen: set[str] = set()
    for ticker, probability, features_raw, result_yes in rows:
        cluster = str(ticker).rsplit("-", 1)[0]
        if cluster in seen:
            continue
        try:
            features = json.loads(features_raw) if isinstance(features_raw, str) else {}
        except (ValueError, TypeError):
            features = {}
        market_prior = features.get("market_implied_yes")
        if not isinstance(market_prior, (int, float)):
            continue
        seen.add(cluster)
        cases.append(HeldOutCase(
            case_id=f"settled-{ticker}",
            event_cluster_id=cluster,
            market_prior_probability=min(0.99, max(0.01, float(market_prior))),
            incumbent_probability=min(0.99, max(0.01, float(probability))),
            result_yes=bool(result_yes),
            evidence_ids=(f"ledger-settlement-{ticker}",),
            settlement_source_reference=f"ledger://settlements/{ticker}",
            settlement_verified=True,
        ))
        if len(cases) >= HELD_OUT_COUNT:
            break
    return tuple(cases)


def settlements_for(conn: sqlite3.Connection, tickers: list[str]) -> dict[str, bool]:
    if not tickers:
        return {}
    marks = ",".join("?" for _ in tickers)
    rows = conn.execute(
        f"SELECT market_ticker, result_yes FROM settlements WHERE market_ticker IN ({marks})",
        tickers,
    ).fetchall()
    return {str(t): bool(r) for t, r in rows}


# The autonomy ledger is a single-writer, non-WAL SQLite file the brain writes
# every cycle. A read-only settlement/held-out read that lands mid-write raises
# OperationalError("database is locked"). Because completion is deferrable, that
# is an expected transient, not a failure -- honored below by returning a
# "busy" note the pass treats as a soft skip.
_LEDGER_BUSY_TIMEOUT_MS = 8000


def _read_ledger_state(
    db_path: str, pending_ids: list[str]
) -> tuple[dict[str, bool], tuple[Any, ...], str | None]:
    """(settled_map, held_out_cases, note): note is None | "busy" | "ledger:<Exc>"."""
    conn = None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=10)
        conn.execute(f"PRAGMA busy_timeout = {_LEDGER_BUSY_TIMEOUT_MS}")
        settled_map = settlements_for(conn, pending_ids)
        held_out = held_out_cases_from_ledger(conn)
        return settled_map, held_out, None
    except sqlite3.OperationalError as exc:
        if "locked" in str(exc).lower() or "busy" in str(exc).lower():
            return {}, (), "busy"
        return {}, (), f"ledger:{type(exc).__name__}"
    except sqlite3.Error as exc:
        return {}, (), f"ledger:{type(exc).__name__}"
    finally:
        if conn is not None:
            conn.close()


def run_shadow_pass(
    *,
    board: dict[str, Any] | None = None,
    db_path: str = "runtime/autonomy/ledger.db",
    max_issues: int = MAX_ISSUES_PER_PASS,
) -> dict[str, Any]:
    """One bounded ignition pass: complete what settled, issue what's open."""
    from autonomy.bet_board import BOARD_PATH
    from dummy.organisms import JsonlEpisodeLedger, issue_episode
    from dummy.organisms.episode import complete_issued_episode
    from dummy.organisms.models import IssuedEpisodeArtifact, VerifiedSettlement

    now = datetime.now(timezone.utc)
    summary: dict[str, Any] = {"at": now.isoformat(), "issued": 0, "completed": 0,
                               "expired": 0, "errors": []}
    if board is None:
        try:
            board = json.loads(BOARD_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            board = {}

    pending = load_pending()
    pending_ids = {str(p.get("market_id")) for p in pending}

    # ---- COMPLETE settled episodes (and expire the abandoned) --------------
    kept: list[dict[str, Any]] = []
    settled_map, held_out, note = _read_ledger_state(
        db_path, [str(p.get("market_id")) for p in pending])
    # Completion is deferrable: pending persists and the next pass retries, so
    # a busy single-writer ledger is a soft skip, never a hard error. ISSUE
    # below touches only the board artifact and always runs.
    if note == "busy":
        summary["ledger_busy"] = True
    elif note is not None:
        summary["errors"].append(note)

    ledger_sink = JsonlEpisodeLedger(EPISODES_PATH)
    for record in pending:
        market_id = str(record.get("market_id"))
        issued_at = _utc(record.get("issued_at") or "") or now
        cluster = str(record.get("event_cluster_id"))
        # Held-out replay may never reuse the decision's own event cluster
        # (EpisodeRequest enforces this); filter per-record so a live cluster
        # collision drops one case rather than failing the whole completion.
        cases = tuple(c for c in held_out if c.event_cluster_id != cluster)
        if market_id in settled_map and len(cases) >= 1:
            try:
                issued = IssuedEpisodeArtifact(record["issued"])
                # The settlement's close MUST equal the issued request's close
                # (EpisodeRequest identity), and clocks obey closed <= settled
                # <= received. The market closes and settles at its nominal
                # close; verified truth is received at the observation instant
                # (or at close when a not-yet-closed market is graded in test).
                close = _utc(record.get("market_close_at") or "") or now
                settlement = VerifiedSettlement(
                    market_id=market_id,
                    event_cluster_id=cluster,
                    result_yes=settled_map[market_id],
                    market_closed_at=close,
                    settled_at=close,
                    received_at=max(close, now),
                    source="autonomy-ledger-settlement",
                    source_reference=f"ledger://settlements/{market_id}",
                    verified=True,
                )
                complete_issued_episode(
                    issued, settlement=settlement,
                    held_out_cases=cases, ledger=ledger_sink)
                summary["completed"] += 1
                continue
            except Exception as exc:
                summary["errors"].append(
                    f"complete:{market_id}:{type(exc).__name__}")
        if (now - issued_at) > timedelta(hours=PENDING_EXPIRY_HOURS):
            summary["expired"] += 1
            continue
        kept.append(record)

    # ---- ISSUE new episodes from the live board ---------------------------
    for row in eligible_rows(board, pending_ids)[:max_issues]:
        try:
            request = build_issue_request(row, str(board.get("generated_at")))
            issued = issue_episode(request)
            kept.append({
                "market_id": request.market_id,
                "event_cluster_id": request.event_cluster_id,
                "issued_at": now.isoformat(),
                "market_close_at": request.market_close_at.isoformat(),
                "issued": issued.to_dict(),
            })
            summary["issued"] += 1
        except Exception as exc:
            summary["errors"].append(
                f"issue:{row.get('ticker')}:{type(exc).__name__}")

    save_pending(kept)
    summary["pending"] = len(kept)
    try:
        with EPISODES_PATH.open(encoding="utf-8") as fh:
            summary["episodes_on_ledger"] = sum(1 for _ in fh)
    except OSError:
        summary["episodes_on_ledger"] = 0
    summary["errors"] = summary["errors"][:10]
    _write_status(summary)
    return summary


def _write_status(summary: dict[str, Any]) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATUS_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(summary, indent=2, sort_keys=True),
                         encoding="utf-8")
    temporary.replace(STATUS_PATH)
