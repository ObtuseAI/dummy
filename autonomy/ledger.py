"""SQLite ledger: decisions, outcomes, calibration, source trust, bankroll curve.

The ledger is the substrate of recursive improvement — every weight update,
stage promotion, and Reflexion lesson traces back to rows here. Append-only
for facts; the only UPDATEs are settlement backfills onto their own rows.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autonomy.ontology import Decision, OutcomeKind, Signal, TradeOutcome

_SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY,
    market_ticker TEXT NOT NULL,
    action TEXT NOT NULL,
    side TEXT NOT NULL,
    price_cents INTEGER NOT NULL,
    count INTEGER NOT NULL,
    ev_cents REAL NOT NULL,
    kelly REAL NOT NULL,
    notional_cents INTEGER NOT NULL,
    probability_yes REAL NOT NULL,
    market_implied_yes REAL,
    sources_used TEXT NOT NULL,
    abstain_reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id TEXT NOT NULL,
    market_ticker TEXT NOT NULL,
    kind TEXT NOT NULL,
    order_id TEXT,
    fill_count INTEGER NOT NULL DEFAULT 0,
    fill_price_cents INTEGER,
    pnl_cents INTEGER,
    broker_contacted INTEGER NOT NULL DEFAULT 0,
    detail TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    market_ticker TEXT NOT NULL,
    probability_yes REAL NOT NULL,
    uncertainty REAL NOT NULL,
    rationale TEXT NOT NULL,
    created_at TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'live'
);
CREATE TABLE IF NOT EXISTS settlements (
    market_ticker TEXT PRIMARY KEY,
    result_yes INTEGER NOT NULL,
    settled_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_trust (
    source TEXT PRIMARY KEY,
    weight REAL NOT NULL,
    brier_sum REAL NOT NULL DEFAULT 0,
    brier_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bankroll_curve (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bankroll_cents INTEGER NOT NULL,
    open_exposure_cents INTEGER NOT NULL,
    stage INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    lesson TEXT NOT NULL,
    evidence TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_outcomes_decision ON outcomes(decision_id);
CREATE INDEX IF NOT EXISTS idx_signals_market ON signals(market_ticker);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AutonomyLedger:
    def __init__(self, db_path: Path | str = Path("runtime/autonomy/ledger.db")):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.executescript(_SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        """Additive migrations for ledgers created before a column existed."""
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(signals)")}
        if "mode" not in columns:
            self._conn.execute("ALTER TABLE signals ADD COLUMN mode TEXT NOT NULL DEFAULT 'live'")

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------------

    def record_signal(self, signal: Signal, mode: str = "live") -> None:
        self._conn.execute(
            "INSERT INTO signals(source, market_ticker, probability_yes, uncertainty, rationale, created_at, mode)"
            " VALUES (?,?,?,?,?,?,?)",
            (signal.source, signal.market_ticker, signal.probability_yes, signal.uncertainty,
             signal.rationale[:500], signal.created_at, mode),
        )
        self._conn.commit()

    def record_decision(self, decision: Decision) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO decisions(decision_id, market_ticker, action, side, price_cents, count,"
            " ev_cents, kelly, notional_cents, probability_yes, market_implied_yes, sources_used,"
            " abstain_reason, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                decision.decision_id, decision.market_ticker, decision.action.value, decision.side,
                decision.price_cents, decision.count, decision.ev_cents_per_contract, decision.kelly_fraction,
                decision.notional_cents, decision.forecast.probability_yes, decision.forecast.market_implied_yes,
                json.dumps(decision.forecast.sources_used, sort_keys=True), decision.abstain_reason,
                decision.created_at,
            ),
        )
        self._conn.commit()

    def record_outcome(self, outcome: TradeOutcome) -> None:
        self._conn.execute(
            "INSERT INTO outcomes(decision_id, market_ticker, kind, order_id, fill_count, fill_price_cents,"
            " pnl_cents, broker_contacted, detail, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                outcome.decision_id, outcome.market_ticker, outcome.kind.value, outcome.order_id,
                outcome.fill_count, outcome.fill_price_cents, outcome.pnl_cents,
                1 if outcome.broker_contacted else 0, json.dumps(outcome.detail, sort_keys=True, default=str),
                outcome.created_at,
            ),
        )
        self._conn.commit()

    def settlement_result(self, market_ticker: str) -> bool | None:
        row = self._conn.execute(
            "SELECT result_yes FROM settlements WHERE market_ticker=?", (market_ticker,)
        ).fetchone()
        return None if row is None else bool(row[0])

    def record_settlement(self, market_ticker: str, result_yes: bool) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO settlements(market_ticker, result_yes, settled_at) VALUES (?,?,?)",
            (market_ticker, 1 if result_yes else 0, _now()),
        )
        self._conn.commit()

    def record_bankroll(self, bankroll_cents: int, open_exposure_cents: int, stage: int) -> None:
        self._conn.execute(
            "INSERT INTO bankroll_curve(bankroll_cents, open_exposure_cents, stage, created_at) VALUES (?,?,?,?)",
            (bankroll_cents, open_exposure_cents, stage, _now()),
        )
        self._conn.commit()

    def record_lesson(self, scope: str, lesson: str, evidence: dict[str, Any] | None = None) -> None:
        self._conn.execute(
            "INSERT INTO lessons(scope, lesson, evidence, created_at) VALUES (?,?,?,?)",
            (scope, lesson[:2000], json.dumps(evidence or {}, sort_keys=True, default=str), _now()),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Trust weights (Blunder-descended: outcome-updated source trust)
    # ------------------------------------------------------------------

    def get_weight(self, source: str, default: float = 1.0) -> float:
        row = self._conn.execute("SELECT weight FROM source_trust WHERE source=?", (source,)).fetchone()
        return float(row[0]) if row else default

    def get_weight_scoped(self, source: str, vertical: str) -> float:
        """Vertical-scoped trust when earned, else the source's global weight.

        Scoped rows use the key convention 'source@VERTICAL'. A source can be
        an authority on crypto and a fish on weather; fusion should know.
        """
        row = self._conn.execute(
            "SELECT weight FROM source_trust WHERE source=?", (f"{source}@{vertical}",)
        ).fetchone()
        if row:
            return float(row[0])
        return self.get_weight(source)

    def all_weights(self) -> dict[str, float]:
        return {r[0]: float(r[1]) for r in self._conn.execute("SELECT source, weight FROM source_trust")}

    def update_weight(self, source: str, weight: float, brier: float | None = None) -> None:
        row = self._conn.execute(
            "SELECT brier_sum, brier_count FROM source_trust WHERE source=?", (source,)
        ).fetchone()
        brier_sum, brier_count = (float(row[0]), int(row[1])) if row else (0.0, 0)
        if brier is not None:
            brier_sum += brier
            brier_count += 1
        self._conn.execute(
            "INSERT OR REPLACE INTO source_trust(source, weight, brier_sum, brier_count, updated_at)"
            " VALUES (?,?,?,?,?)",
            (source, weight, brier_sum, brier_count, _now()),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Queries for the learner / status surface
    # ------------------------------------------------------------------

    def open_decisions(self, scope: str | None = None) -> list[dict[str, Any]]:
        """Decisions whose latest outcome is an open position, not yet
        settled/canceled/expired.

        scope: None = all books; "live" = broker positions (ACCEPTED/FILLED);
        "shadow" = shadow-book positions. Live and shadow sessions run
        concurrently against one ledger — a live brain must never count the
        shadow book against its slots, and vice versa.
        """
        kinds = {"live": "('ACCEPTED', 'FILLED')", "shadow": "('SHADOW')"}.get(
            scope or "", "('ACCEPTED', 'FILLED', 'SHADOW')")
        rows = self._conn.execute(
            f"""
            SELECT d.decision_id, d.market_ticker, d.side, d.price_cents, d.count, o.kind, o.order_id
            FROM decisions d
            JOIN outcomes o ON o.decision_id = d.decision_id
            WHERE o.id = (SELECT MAX(id) FROM outcomes WHERE decision_id = d.decision_id)
              AND o.kind IN {kinds}
            """
        ).fetchall()
        keys = ["decision_id", "market_ticker", "side", "price_cents", "count", "kind", "order_id"]
        return [dict(zip(keys, r)) for r in rows]

    def signals_for_market(self, market_ticker: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT source, probability_yes, uncertainty, created_at FROM signals WHERE market_ticker=?",
            (market_ticker,),
        ).fetchall()
        return [
            {"source": r[0], "probability_yes": r[1], "uncertainty": r[2], "created_at": r[3]} for r in rows
        ]

    def unsettled_traded_markets(self) -> list[str]:
        rows = self._conn.execute(
            """
            SELECT DISTINCT d.market_ticker FROM decisions d
            WHERE d.action != 'ABSTAIN'
              AND d.market_ticker NOT IN (SELECT market_ticker FROM settlements)
            """
        ).fetchall()
        return [r[0] for r in rows]

    def unsettled_forecast_markets(self, max_age_days: float = 7.0) -> list[str]:
        """Every market we recently opined on that has no settlement yet.

        This is the phantom-grading feed: calibration evidence comes from every
        forecast the machine makes, not just the handful it traded. Bounded by
        signal age so the set can't grow without limit.
        """
        from datetime import timedelta

        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
        rows = self._conn.execute(
            """
            SELECT DISTINCT s.market_ticker FROM signals s
            WHERE s.created_at >= ?
              AND s.market_ticker NOT IN (SELECT market_ticker FROM settlements)
            """,
            (cutoff,),
        ).fetchall()
        return [r[0] for r in rows]

    def evidence_split(self) -> dict[str, int]:
        """Settled-market counts by evidence provenance (live shadow vs retro)."""
        live = self._conn.execute(
            """
            SELECT COUNT(DISTINCT st.market_ticker) FROM settlements st
            WHERE EXISTS (SELECT 1 FROM signals s
                          WHERE s.market_ticker = st.market_ticker AND s.mode = 'live')
            """
        ).fetchone()
        retro_only = self._conn.execute(
            """
            SELECT COUNT(DISTINCT st.market_ticker) FROM settlements st
            WHERE NOT EXISTS (SELECT 1 FROM signals s
                              WHERE s.market_ticker = st.market_ticker AND s.mode = 'live')
              AND EXISTS (SELECT 1 FROM signals s
                          WHERE s.market_ticker = st.market_ticker AND s.mode = 'retro')
            """
        ).fetchone()
        return {"live_settled": int(live[0]), "retro_settled": int(retro_only[0])}

    def performance_summary(self) -> dict[str, Any]:
        pnl = self._conn.execute(
            "SELECT COALESCE(SUM(pnl_cents),0), COUNT(*) FROM outcomes WHERE pnl_cents IS NOT NULL"
        ).fetchone()
        settled = self._conn.execute("SELECT COUNT(*) FROM settlements").fetchone()
        decisions = self._conn.execute(
            "SELECT COUNT(*), SUM(CASE WHEN action='ABSTAIN' THEN 1 ELSE 0 END) FROM decisions"
        ).fetchone()
        lessons = self._conn.execute("SELECT COUNT(*) FROM lessons").fetchone()
        return {
            "realized_pnl_cents": int(pnl[0]),
            "outcomes_with_pnl": int(pnl[1]),
            "settlements_recorded": int(settled[0]),
            "decisions_total": int(decisions[0] or 0),
            "decisions_abstained": int(decisions[1] or 0),
            "lessons_recorded": int(lessons[0]),
            "source_weights": self.all_weights(),
        }
