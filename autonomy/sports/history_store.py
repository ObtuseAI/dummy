"""Phase 1: the sports historical data lake — a point-in-time store.

A persistent, multi-season SQLite store of free/public sports data (game
results + boxscores + play-by-play + odds lines + injuries), the foundation the
analytics foundry and the walk-forward backtester read from. Every game can
carry ``result_available_at`` (when the source made the result knowable),
``received_at`` (when Dummy observed that version), and ``provenance_quality``.
Each boxscore feature can separately carry ``source_available_at`` and
``received_at``. Historical evaluation is fail-closed: rows missing their
required availability evidence are not eligible to train or grade a model.

Point-in-time is the whole point: :meth:`games_before` and :meth:`team_form`
return only games that had already **finished** strictly before the given
instant, so a model's cold-start prior or a walk-forward replay can never see a
result that hadn't happened yet. Pure stdlib (sqlite3 + json), house style:
no numpy/pandas. Own DB file (never the ledger), with its own retention.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

DEFAULT_PATH = Path("runtime/autonomy/sports_history.db")

# A game is "complete" (safe to read as history) only in these statuses.
_FINAL_STATUSES = ("final", "post", "closed", "complete", "completed")


# Only these provenance classes may enter historical evaluation. Flat-file
# retro backfills without a source publication timestamp deliberately remain
# unknown and are quarantined from backtests.
EVALUATION_PROVENANCE_QUALITIES = frozenset({"observed_at_receipt", "source_reported"})


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse an ISO-8601 timestamp for conservative ordering checks."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _evaluation_rejection_reason(game: dict[str, Any]) -> str | None:
    """Return why a completed game is unsafe for point-in-time evaluation."""
    if game.get("status") not in _FINAL_STATUSES:
        return "not_final"
    if game.get("home_score") is None or game.get("away_score") is None:
        return "missing_score"
    if not game.get("result_available_at") or not game.get("received_at"):
        return "unknown_availability"
    if game.get("provenance_quality") not in EVALUATION_PROVENANCE_QUALITIES:
        return "untrusted_provenance"
    start = _parse_timestamp(game.get("start_time"))
    available = _parse_timestamp(game.get("result_available_at"))
    received = _parse_timestamp(game.get("received_at"))
    if start is None or available is None or received is None:
        return "invalid_timestamp"
    if available < start or received < available:
        return "invalid_timestamp_order"
    return None


class SportsHistoryStore:
    """Point-in-time store for multi-season sports history."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    # ---- schema ----------------------------------------------------------
    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS games(
                game_id TEXT PRIMARY KEY,
                league TEXT NOT NULL, season INTEGER,
                start_time TEXT NOT NULL, status TEXT NOT NULL,
                home TEXT, away TEXT,
                home_score INTEGER, away_score INTEGER,
                venue TEXT, neutral INTEGER DEFAULT 0,
                as_of TEXT, source TEXT, provenance_url TEXT,
                result_available_at TEXT, received_at TEXT,
                provenance_quality TEXT,
                extra TEXT
            );
            CREATE INDEX IF NOT EXISTS ix_games_league_time ON games(league, start_time);
            CREATE INDEX IF NOT EXISTS ix_games_season ON games(league, season);

            CREATE TABLE IF NOT EXISTS boxscores(
                game_id TEXT NOT NULL, team TEXT NOT NULL, player TEXT,
                stat TEXT NOT NULL, value REAL,
                as_of TEXT, source TEXT,
                source_available_at TEXT, received_at TEXT,
                PRIMARY KEY (game_id, team, player, stat)
            );
            CREATE INDEX IF NOT EXISTS ix_box_game ON boxscores(game_id);

            CREATE TABLE IF NOT EXISTS plays(
                play_id TEXT PRIMARY KEY, game_id TEXT NOT NULL,
                league TEXT, period INTEGER, clock TEXT, ordinal INTEGER,
                data TEXT, as_of TEXT, source TEXT
            );
            CREATE INDEX IF NOT EXISTS ix_plays_game ON plays(game_id, ordinal);

            CREATE TABLE IF NOT EXISTS lines(
                ticker TEXT NOT NULL, book TEXT NOT NULL, ts TEXT NOT NULL,
                market_type TEXT, price REAL, point REAL, is_close INTEGER DEFAULT 0,
                game_id TEXT, source TEXT,
                PRIMARY KEY (ticker, book, ts)
            );
            CREATE INDEX IF NOT EXISTS ix_lines_game ON lines(game_id);

            CREATE TABLE IF NOT EXISTS ingest_log(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL, league TEXT, date_range TEXT,
                status TEXT, rows INTEGER, http TEXT, at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS ix_ingest ON ingest_log(source, league, id);

            CREATE TABLE IF NOT EXISTS research_holdout_consumptions(
                seal_key TEXT PRIMARY KEY,
                league TEXT NOT NULL, holdout_season INTEGER NOT NULL,
                model TEXT NOT NULL, holdout_ids_hash TEXT NOT NULL,
                selection_ids_hash TEXT NOT NULL, consumed_at TEXT NOT NULL,
                manifest_version TEXT,
                holdout_manifest_hash TEXT, holdout_content_hash TEXT,
                holdout_outcomes_hash TEXT,
                selection_manifest_hash TEXT, selection_content_hash TEXT,
                selection_outcomes_hash TEXT,
                execution_authority INTEGER NOT NULL DEFAULT 0,
                promotion_authority INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        # Existing lakes predate the point-in-time evidence columns. Do not
        # backfill them from start_time/as_of: unknown availability must remain
        # unknown and therefore excluded from historical evaluation.
        columns = {str(row[1]) for row in cur.execute("PRAGMA table_info(games)")}
        for name in ("result_available_at", "received_at", "provenance_quality"):
            if name not in columns:
                try:
                    cur.execute(f"ALTER TABLE games ADD COLUMN {name} TEXT")
                except sqlite3.OperationalError:
                    # Another process may have completed the idempotent
                    # migration after our PRAGMA snapshot.
                    current = {
                        str(row[1]) for row in cur.execute("PRAGMA table_info(games)")
                    }
                    if name not in current:
                        raise
        cur.execute(
            "CREATE INDEX IF NOT EXISTS ix_games_result_availability "
            "ON games(league, result_available_at, received_at)"
        )
        # Feature arrival is independent of the game-result envelope. Legacy
        # boxscores remain NULL here: neither as_of nor game start/result time
        # proves when an individual feature version reached Dummy.
        boxscore_columns = {
            str(row[1]) for row in cur.execute("PRAGMA table_info(boxscores)")
        }
        for name in ("source_available_at", "received_at"):
            if name not in boxscore_columns:
                try:
                    cur.execute(f"ALTER TABLE boxscores ADD COLUMN {name} TEXT")
                except sqlite3.OperationalError:
                    current = {
                        str(row[1])
                        for row in cur.execute("PRAGMA table_info(boxscores)")
                    }
                    if name not in current:
                        raise
        cur.execute(
            "CREATE INDEX IF NOT EXISTS ix_box_feature_availability "
            "ON boxscores(game_id, source_available_at, received_at)"
        )
        # V1 claims remain immutable evidence. Add nullable manifest columns
        # without fabricating hashes for those historical rows; the permanent
        # scope lock below still prevents a V1 claim from being reopened by a
        # changed game list or corrected result.
        holdout_columns = {
            str(row[1])
            for row in cur.execute("PRAGMA table_info(research_holdout_consumptions)")
        }
        for name in (
            "manifest_version",
            "holdout_manifest_hash",
            "holdout_content_hash",
            "holdout_outcomes_hash",
            "selection_manifest_hash",
            "selection_content_hash",
            "selection_outcomes_hash",
        ):
            if name not in holdout_columns:
                try:
                    cur.execute(
                        f"ALTER TABLE research_holdout_consumptions ADD COLUMN {name} TEXT"
                    )
                except sqlite3.OperationalError:
                    current = {
                        str(row[1])
                        for row in cur.execute(
                            "PRAGMA table_info(research_holdout_consumptions)"
                        )
                    }
                    if name not in current:
                        raise
        cur.execute(
            "CREATE INDEX IF NOT EXISTS ix_research_holdout_scope "
            "ON research_holdout_consumptions(league, holdout_season, model)"
        )
        try:
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_research_holdout_scope_v2 "
                "ON research_holdout_consumptions("
                "lower(trim(league)), holdout_season, lower(trim(model)))"
            )
        except sqlite3.IntegrityError:
            # Preserve every pre-existing conflicting claim rather than
            # deleting or rewriting evidence. The trigger below blocks all
            # additional claims for any already-consumed scope.
            pass
        cur.executescript(
            """
            CREATE TRIGGER IF NOT EXISTS trg_research_holdout_require_v2_manifest
            BEFORE INSERT ON research_holdout_consumptions
            WHEN NEW.manifest_version IS NULL
              OR trim(NEW.manifest_version) = ''
              OR length(NEW.seal_key) != 64
              OR lower(NEW.seal_key) GLOB '*[^0-9a-f]*'
              OR length(NEW.holdout_ids_hash) != 64
              OR lower(NEW.holdout_ids_hash) GLOB '*[^0-9a-f]*'
              OR length(NEW.selection_ids_hash) != 64
              OR lower(NEW.selection_ids_hash) GLOB '*[^0-9a-f]*'
              OR NEW.holdout_manifest_hash IS NULL
              OR length(NEW.holdout_manifest_hash) != 64
              OR lower(NEW.holdout_manifest_hash) GLOB '*[^0-9a-f]*'
              OR NEW.holdout_content_hash IS NULL
              OR length(NEW.holdout_content_hash) != 64
              OR lower(NEW.holdout_content_hash) GLOB '*[^0-9a-f]*'
              OR NEW.holdout_outcomes_hash IS NULL
              OR length(NEW.holdout_outcomes_hash) != 64
              OR lower(NEW.holdout_outcomes_hash) GLOB '*[^0-9a-f]*'
              OR NEW.selection_manifest_hash IS NULL
              OR length(NEW.selection_manifest_hash) != 64
              OR lower(NEW.selection_manifest_hash) GLOB '*[^0-9a-f]*'
              OR NEW.selection_content_hash IS NULL
              OR length(NEW.selection_content_hash) != 64
              OR lower(NEW.selection_content_hash) GLOB '*[^0-9a-f]*'
              OR NEW.selection_outcomes_hash IS NULL
              OR length(NEW.selection_outcomes_hash) != 64
              OR lower(NEW.selection_outcomes_hash) GLOB '*[^0-9a-f]*'
            BEGIN
                SELECT RAISE(ABORT, 'research holdout requires complete SHA-256 manifests');
            END;

            CREATE TRIGGER IF NOT EXISTS trg_research_holdout_scope_once
            BEFORE INSERT ON research_holdout_consumptions
            WHEN EXISTS(
                SELECT 1 FROM research_holdout_consumptions
                WHERE lower(trim(league)) = lower(trim(NEW.league))
                  AND holdout_season = NEW.holdout_season
                  AND lower(trim(model)) = lower(trim(NEW.model))
            )
            BEGIN
                SELECT RAISE(ABORT, 'research holdout scope already consumed');
            END;

            CREATE TRIGGER IF NOT EXISTS trg_research_holdout_immutable_update
            BEFORE UPDATE ON research_holdout_consumptions
            BEGIN
                SELECT RAISE(ABORT, 'research holdout claims are immutable');
            END;

            CREATE TRIGGER IF NOT EXISTS trg_research_holdout_immutable_delete
            BEFORE DELETE ON research_holdout_consumptions
            BEGIN
                SELECT RAISE(ABORT, 'research holdout claims are immutable');
            END;
            """
        )
        self.conn.commit()

    # ---- writes ----------------------------------------------------------
    def upsert_game(self, game: dict[str, Any]) -> None:
        self.upsert_games([game])

    def upsert_games(self, games: Iterable[dict[str, Any]]) -> int:
        rows = [
            (
                g["game_id"], g["league"], g.get("season"),
                g["start_time"], g.get("status", "scheduled"),
                g.get("home"), g.get("away"), g.get("home_score"), g.get("away_score"),
                g.get("venue"), 1 if g.get("neutral") else 0,
                g.get("as_of") or g.get("received_at"), g.get("source"), g.get("provenance_url"),
                g.get("result_available_at"), g.get("received_at"),
                g.get("provenance_quality") or "unknown",
                json.dumps(g.get("extra")) if g.get("extra") is not None else None,
            )
            for g in games
        ]
        self.conn.executemany(
            """INSERT INTO games(game_id,league,season,start_time,status,home,away,
                   home_score,away_score,venue,neutral,as_of,source,provenance_url,
                   result_available_at,received_at,provenance_quality,extra)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(game_id) DO UPDATE SET
                   season=excluded.season, start_time=excluded.start_time,
                   status=excluded.status, home=excluded.home, away=excluded.away,
                   home_score=excluded.home_score, away_score=excluded.away_score,
                   venue=excluded.venue, neutral=excluded.neutral,
                   as_of=excluded.as_of, source=excluded.source,
                   provenance_url=excluded.provenance_url,
                   -- Observation always outranks derivation: a row whose
                   -- availability was witnessed at receipt is never downgraded
                   -- by a later derived source_reported backfill.
                   result_available_at=CASE
                       WHEN games.provenance_quality='observed_at_receipt'
                            AND excluded.provenance_quality='source_reported'
                       THEN games.result_available_at
                       ELSE COALESCE(
                           excluded.result_available_at, games.result_available_at
                       )
                   END,
                   received_at=CASE
                       WHEN games.provenance_quality='observed_at_receipt'
                            AND excluded.provenance_quality='source_reported'
                       THEN games.received_at
                       WHEN excluded.result_available_at IS NOT NULL
                       THEN excluded.received_at
                       ELSE COALESCE(games.received_at, excluded.received_at)
                   END,
                   provenance_quality=CASE
                       WHEN games.provenance_quality='observed_at_receipt'
                            AND excluded.provenance_quality='source_reported'
                       THEN games.provenance_quality
                       WHEN excluded.result_available_at IS NOT NULL
                       THEN excluded.provenance_quality
                       ELSE COALESCE(games.provenance_quality, excluded.provenance_quality)
                   END,
                   extra=excluded.extra""",
            rows,
        )
        self.conn.commit()
        return len(rows)

    def record_lines(self, lines: Iterable[dict[str, Any]]) -> int:
        """Upsert odds lines (open/close snapshots) keyed by (ticker, book, ts)."""
        rows = [
            (
                ln["ticker"], ln.get("book", "unknown"), ln["ts"], ln.get("market_type"),
                ln.get("price"), ln.get("point"), 1 if ln.get("is_close") else 0,
                ln.get("game_id"), ln.get("source"),
            )
            for ln in lines
        ]
        if not rows:
            return 0
        self.conn.executemany(
            """INSERT INTO lines(ticker,book,ts,market_type,price,point,is_close,game_id,source)
               VALUES(?,?,?,?,?,?,?,?,?)
               ON CONFLICT(ticker,book,ts) DO UPDATE SET
                   market_type=excluded.market_type, price=excluded.price,
                   point=excluded.point, is_close=excluded.is_close,
                   game_id=excluded.game_id, source=excluded.source""",
            rows,
        )
        self.conn.commit()
        return len(rows)

    def lines_for(self, game_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM lines WHERE game_id = ? ORDER BY ticker, ts", (game_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def record_team_boxscores(self, rows: Iterable[dict[str, Any]]) -> int:
        """Upsert team features, including their source/receipt-time envelope."""
        tuples = [
            (r["game_id"], r["team"], "", stat, float(val),
             r.get("as_of"), r.get("source", "espn"),
             r.get("source_available_at"), r.get("received_at"))
            for r in rows
            for stat, val in (r.get("stats") or {}).items()
        ]
        if not tuples:
            return 0
        self.conn.executemany(
            """INSERT INTO boxscores(
                   game_id,team,player,stat,value,as_of,source,
                   source_available_at,received_at
               )
               VALUES(?,?,?,?,?,?,?,?,?)
               ON CONFLICT(game_id,team,player,stat) DO UPDATE SET
                   value=excluded.value, as_of=excluded.as_of, source=excluded.source,
                   source_available_at=CASE
                       WHEN boxscores.value = excluded.value
                            AND julianday(boxscores.source_available_at) IS NOT NULL
                            AND julianday(boxscores.received_at) IS NOT NULL
                            AND julianday(boxscores.received_at)
                                >= julianday(boxscores.source_available_at)
                       THEN boxscores.source_available_at
                       ELSE excluded.source_available_at
                   END,
                   received_at=CASE
                       WHEN boxscores.value = excluded.value
                            AND julianday(boxscores.source_available_at) IS NOT NULL
                            AND julianday(boxscores.received_at) IS NOT NULL
                            AND julianday(boxscores.received_at)
                                >= julianday(boxscores.source_available_at)
                       THEN boxscores.received_at
                       ELSE excluded.received_at
                   END""",
            tuples,
        )
        self.conn.commit()
        return len(tuples)

    def record_player_boxscores(self, rows: Iterable[dict[str, Any]]) -> int:
        """Upsert player features, including their source/receipt-time envelope."""
        tuples = [
            (r["game_id"], r["team"], r["player"], r["stat"], float(r["value"]),
             r.get("as_of"), r.get("source", "espn"),
             r.get("source_available_at"), r.get("received_at"))
            for r in rows
            if r.get("player")
        ]
        if not tuples:
            return 0
        self.conn.executemany(
            """INSERT INTO boxscores(
                   game_id,team,player,stat,value,as_of,source,
                   source_available_at,received_at
               )
               VALUES(?,?,?,?,?,?,?,?,?)
               ON CONFLICT(game_id,team,player,stat) DO UPDATE SET
                   value=excluded.value, as_of=excluded.as_of, source=excluded.source,
                   source_available_at=CASE
                       WHEN boxscores.value = excluded.value
                            AND julianday(boxscores.source_available_at) IS NOT NULL
                            AND julianday(boxscores.received_at) IS NOT NULL
                            AND julianday(boxscores.received_at)
                                >= julianday(boxscores.source_available_at)
                       THEN boxscores.source_available_at
                       ELSE excluded.source_available_at
                   END,
                   received_at=CASE
                       WHEN boxscores.value = excluded.value
                            AND julianday(boxscores.source_available_at) IS NOT NULL
                            AND julianday(boxscores.received_at) IS NOT NULL
                            AND julianday(boxscores.received_at)
                                >= julianday(boxscores.source_available_at)
                       THEN boxscores.received_at
                       ELSE excluded.received_at
                   END""",
            tuples,
        )
        self.conn.commit()
        return len(tuples)

    def player_game_log(
        self, player: str, as_of: str, *, league: str | None = None, n: int = 20,
    ) -> list[dict[str, Any]]:
        """A player's recent games (most recent first) as pivoted stat dicts.

        Point-in-time: every returned feature version was source-available and
        received strictly before ``as_of``. Legacy/unknown-arrival rows remain
        quarantined. Each entry carries ``game_id``, ``start_time`` and every
        eligible stat (minutes, points, rebounds, ...).
        """
        finals = ",".join("?" * len(_FINAL_STATUSES))
        feature_sql, feature_params = self._feature_availability_sql(
            as_of, table_alias="b", start_time_sql="g.start_time",
        )
        params: list[Any] = [player, as_of, *_FINAL_STATUSES, *feature_params]
        league_clause = ""
        if league is not None:
            league_clause = " AND g.league = ?"
            params.append(league)
        rows = self.conn.execute(
            "SELECT b.game_id, g.start_time, b.stat, b.value "
            "FROM boxscores b JOIN games g ON g.game_id = b.game_id "
            "WHERE b.player = ? "
            "AND julianday(g.start_time) < julianday(?) "
            f"AND g.status IN ({finals}) "
            f"{feature_sql}" + league_clause +
            " ORDER BY g.start_time DESC",
            params,
        ).fetchall()
        by_game: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for game_id, start_time, stat, value in rows:
            entry = by_game.get(game_id)
            if entry is None:
                entry = {"game_id": game_id, "start_time": start_time}
                by_game[game_id] = entry
                order.append(game_id)
            entry[str(stat)] = float(value)
        return [by_game[g] for g in order[:int(n)]]

    def game_ids_missing_boxscores(self, league: str, limit: int | None = None) -> list[str]:
        """Completed games without a valid feature-arrival envelope.

        Legacy rows with unknown arrival remain queued so a fresh observation
        can repair them without inventing historical timestamps.
        """
        finals = ",".join("?" * len(_FINAL_STATUSES))
        sql = (
            "SELECT g.game_id FROM games g LEFT JOIN boxscores b "
            "ON b.game_id = g.game_id "
            "AND julianday(b.source_available_at) IS NOT NULL "
            "AND julianday(b.received_at) IS NOT NULL "
            "AND julianday(b.source_available_at) >= julianday(g.start_time) "
            "AND julianday(b.received_at) >= julianday(b.source_available_at) "
            f"WHERE g.league = ? AND g.status IN ({finals}) AND b.game_id IS NULL "
            f"GROUP BY g.game_id ORDER BY g.start_time DESC"
        )
        params: list[Any] = [league, *_FINAL_STATUSES]
        if limit:
            sql += " LIMIT ?"
            params.append(int(limit))
        return [r[0] for r in self.conn.execute(sql, params).fetchall()]

    def team_stat_sums_before(
        self, team: str, as_of: str, league: str, *,
        require_known_availability: bool = False,
    ) -> dict[str, Any] | None:
        """Point-in-time sums of strictly pre-decision team feature versions."""
        finals = ",".join("?" * len(_FINAL_STATUSES))
        availability_sql, availability_params = self._availability_sql(
            as_of, require_known_availability, table_alias="g",
        )
        feature_sql, feature_params = self._feature_availability_sql(
            as_of, table_alias="b", start_time_sql="g.start_time",
        )
        rows = self.conn.execute(
            f"""WITH eligible AS (
                    SELECT b.game_id, b.stat, b.value
                    FROM games g JOIN boxscores b ON b.game_id = g.game_id
                    WHERE b.team = ? AND b.player = '' AND g.league = ?
                      AND julianday(g.start_time) < julianday(?)
                      AND g.status IN ({finals})
                      {feature_sql}
                      {availability_sql}
                )
                SELECT stat, SUM(value),
                       (SELECT COUNT(DISTINCT game_id) FROM eligible)
                FROM eligible GROUP BY stat""",
            (
                team, league, as_of, *_FINAL_STATUSES,
                *feature_params, *availability_params,
            ),
        ).fetchall()
        if not rows:
            return None
        return {
            "sums": {str(stat): value for stat, value, _games in rows},
            "games": int(rows[0][2]),
        }

    def four_factor_sums_before(
        self, team: str, as_of: str, league: str, *,
        require_known_availability: bool = False,
    ) -> dict[str, Any] | None:
        """Strictly pre-decision own/opponent sums over fully paired games."""
        finals = ",".join("?" * len(_FINAL_STATUSES))
        availability_sql, availability_params = self._availability_sql(
            as_of, require_known_availability, table_alias="g",
        )
        feature_sql, feature_params = self._feature_availability_sql(
            as_of, table_alias="b", start_time_sql="g.start_time",
        )
        rows = self.conn.execute(
            f"""WITH eligible_rows AS (
                    SELECT b.game_id, b.team, b.stat, b.value
                    FROM games g JOIN boxscores b ON b.game_id = g.game_id
                    WHERE g.league = ?
                      AND (g.home = ? OR g.away = ?)
                      AND (b.team = g.home OR b.team = g.away)
                      AND b.player = ''
                      AND julianday(g.start_time) < julianday(?)
                      AND g.status IN ({finals})
                      {feature_sql}
                      {availability_sql}
                ),
                eligible_games AS (
                    SELECT game_id FROM eligible_rows
                    GROUP BY game_id
                    HAVING MAX(CASE WHEN team = ? THEN 1 ELSE 0 END) = 1
                       AND MAX(CASE WHEN team != ? THEN 1 ELSE 0 END) = 1
                )
                SELECT CASE WHEN r.team = ? THEN 'off' ELSE 'def' END,
                       r.stat, SUM(r.value),
                       (SELECT COUNT(*) FROM eligible_games)
                FROM eligible_rows r
                JOIN eligible_games eg ON eg.game_id = r.game_id
                GROUP BY CASE WHEN r.team = ? THEN 'off' ELSE 'def' END, r.stat""",
            (
                league, team, team, as_of, *_FINAL_STATUSES,
                *feature_params, *availability_params,
                team, team, team, team,
            ),
        ).fetchall()
        if not rows:
            return None
        own = {str(stat): value for side, stat, value, _games in rows if side == "off"}
        opp = {str(stat): value for side, stat, value, _games in rows if side == "def"}
        if not own or not opp:
            return None
        return {"off": own, "def": opp, "games": int(rows[0][3])}

    def record_ingest(
        self, source: str, league: str | None, date_range: str | None, *,
        status: str, rows: int, http: dict[str, Any] | None = None,
    ) -> None:
        self.conn.execute(
            "INSERT INTO ingest_log(source,league,date_range,status,rows,http) VALUES(?,?,?,?,?,?)",
            (source, league, date_range, status, int(rows), json.dumps(http or {})),
        )
        self.conn.commit()

    # ---- point-in-time reads --------------------------------------------
    def games_before(
        self, as_of: str, league: str | None = None, season: int | None = None, *,
        require_known_availability: bool = False,
    ) -> list[dict[str, Any]]:
        """Completed games that started strictly before ``as_of`` (most recent
        first). Never returns a scheduled/in-progress game — no future leakage."""
        start_time_sql = (
            "julianday(start_time) < julianday(?)"
            if require_known_availability else "start_time < ?"
        )
        clause = [start_time_sql, "status IN (%s)" % ",".join("?" * len(_FINAL_STATUSES))]
        params: list[Any] = [as_of, *_FINAL_STATUSES]
        availability_sql, availability_params = self._availability_sql(
            as_of, require_known_availability, prefix=""
        )
        if availability_sql:
            clause.append(availability_sql)
            params.extend(availability_params)
        if league is not None:
            clause.append("league = ?")
            params.append(league)
        if season is not None:
            clause.append("season = ?")
            params.append(season)
        rows = self.conn.execute(
            "SELECT * FROM games WHERE " + " AND ".join(clause) + " ORDER BY start_time DESC",
            params,
        ).fetchall()
        return [self._row(r) for r in rows]

    def team_form(
        self, team: str, as_of: str, league: str | None = None, n: int = 20, *,
        require_known_availability: bool = False,
    ) -> list[dict[str, Any]]:
        """The team's last ``n`` completed games before ``as_of`` (most recent
        first) — the point-in-time information set for a cold-start prior."""
        params: list[Any] = [as_of, *_FINAL_STATUSES, team, team]
        start_time_sql = (
            "julianday(start_time) < julianday(?)"
            if require_known_availability else "start_time < ?"
        )
        clause = start_time_sql + " AND status IN (%s) AND (home = ? OR away = ?)" % (
            ",".join("?" * len(_FINAL_STATUSES))
        )
        availability_sql, availability_params = self._availability_sql(
            as_of, require_known_availability
        )
        clause += availability_sql
        params.extend(availability_params)
        if league is not None:
            clause += " AND league = ?"
            params.append(league)
        rows = self.conn.execute(
            "SELECT * FROM games WHERE " + clause + " ORDER BY start_time DESC LIMIT ?",
            [*params, int(n)],
        ).fetchall()
        return [self._row(r) for r in rows]

    def evaluation_games(
        self, league: str | None = None, season: int | None = None,
    ) -> list[dict[str, Any]]:
        """Completed games safe to use as historical evaluation targets.

        Unlike :meth:`games`, this is deliberately fail-closed. A retro row
        with a final score but no defensible availability/receipt timestamps is
        not evidence and is omitted.
        """
        return [
            game for game in self.games(league=league, season=season)
            if _evaluation_rejection_reason(game) is None
        ]

    def evaluation_eligibility(
        self, league: str | None = None, season: int | None = None,
    ) -> dict[str, Any]:
        """Explain how many final rows pass the strict historical-data gate."""
        reasons: dict[str, int] = {}
        qualities: dict[str, int] = {}
        sources: dict[str, int] = {}
        candidates = 0
        eligible = 0
        for game in self.games(league=league, season=season):
            if game.get("status") not in _FINAL_STATUSES:
                continue
            candidates += 1
            quality = str(game.get("provenance_quality") or "unknown")
            source = str(game.get("source") or "unknown")
            qualities[quality] = qualities.get(quality, 0) + 1
            sources[source] = sources.get(source, 0) + 1
            reason = _evaluation_rejection_reason(game)
            if reason is None:
                eligible += 1
            else:
                reasons[reason] = reasons.get(reason, 0) + 1
        return {
            "final_candidates": candidates,
            "eligible": eligible,
            "excluded": candidates - eligible,
            "rejection_reasons": dict(sorted(reasons.items())),
            "provenance_quality_counts": dict(sorted(qualities.items())),
            "source_counts": dict(sorted(sources.items())),
            "accepted_provenance_qualities": sorted(EVALUATION_PROVENANCE_QUALITIES),
        }

    def games(
        self, league: str | None = None, season: int | None = None,
    ) -> list[dict[str, Any]]:
        clause, params = [], []
        if league is not None:
            clause.append("league = ?")
            params.append(league)
        if season is not None:
            clause.append("season = ?")
            params.append(season)
        sql = "SELECT * FROM games"
        if clause:
            sql += " WHERE " + " AND ".join(clause)
        sql += " ORDER BY start_time"
        return [self._row(r) for r in self.conn.execute(sql, params).fetchall()]

    def last_ingest(self, source: str, league: str | None = None) -> dict[str, Any] | None:
        if league is None:
            row = self.conn.execute(
                "SELECT * FROM ingest_log WHERE source=? ORDER BY id DESC LIMIT 1", (source,)
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT * FROM ingest_log WHERE source=? AND league=? ORDER BY id DESC LIMIT 1",
                (source, league),
            ).fetchone()
        if row is None:
            return None
        out = dict(row)
        try:
            out["http"] = json.loads(out.get("http") or "{}")
        except Exception:  # noqa: BLE001
            out["http"] = {}
        return out

    def counts(self) -> dict[str, int]:
        return {
            t: self.conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("games", "boxscores", "plays", "lines")
        }

    def claim_research_holdout(
        self, *, seal_key: str, league: str, holdout_season: int, model: str,
        holdout_ids_hash: str, selection_ids_hash: str,
        manifest_version: str, holdout_manifest_hash: str,
        holdout_content_hash: str, holdout_outcomes_hash: str,
        selection_manifest_hash: str, selection_content_hash: str,
        selection_outcomes_hash: str, consumed_at: str,
    ) -> bool:
        """Atomically consume a sealed holdout once, with no live authority.

        The permanent scope lock is ``(league, holdout_season, model)``. A
        changed ID set, content row, or outcome therefore cannot mint a fresh
        claim. V2 claims also bind the immutable selection/holdout manifests.
        """
        hashes = (
            seal_key,
            holdout_ids_hash,
            selection_ids_hash,
            holdout_manifest_hash,
            holdout_content_hash,
            holdout_outcomes_hash,
            selection_manifest_hash,
            selection_content_hash,
            selection_outcomes_hash,
        )
        if (
            not str(manifest_version).strip()
            or any(
                len(str(value)) != 64
                or any(ch not in "0123456789abcdef" for ch in str(value).lower())
                for value in hashes
            )
        ):
            raise ValueError("research holdout claims require complete SHA-256 manifests")
        normalized_league = str(league).strip().lower()
        normalized_model = str(model).strip().lower()
        if not normalized_league or not normalized_model:
            raise ValueError("research holdout league and model are required")
        try:
            self.conn.execute(
                """INSERT INTO research_holdout_consumptions(
                       seal_key,league,holdout_season,model,holdout_ids_hash,
                       selection_ids_hash,manifest_version,
                       holdout_manifest_hash,holdout_content_hash,
                       holdout_outcomes_hash,selection_manifest_hash,
                       selection_content_hash,selection_outcomes_hash,
                       consumed_at,execution_authority,promotion_authority
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,0)""",
                (
                    seal_key, normalized_league, int(holdout_season),
                    normalized_model, holdout_ids_hash, selection_ids_hash,
                    manifest_version, holdout_manifest_hash,
                    holdout_content_hash, holdout_outcomes_hash,
                    selection_manifest_hash, selection_content_hash,
                    selection_outcomes_hash, consumed_at,
                ),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False

    def research_holdout_claim(self, seal_key: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM research_holdout_consumptions WHERE seal_key=?", (seal_key,)
        ).fetchone()
        return None if row is None else dict(row)

    def research_holdout_claims_for_scope(
        self, *, league: str, holdout_season: int, model: str,
    ) -> list[dict[str, Any]]:
        """Every immutable claim for a scope, including preserved legacy conflicts."""
        rows = self.conn.execute(
            """SELECT * FROM research_holdout_consumptions
               WHERE lower(trim(league)) = lower(trim(?))
                 AND holdout_season = ?
                 AND lower(trim(model)) = lower(trim(?))
               ORDER BY consumed_at, seal_key""",
            (str(league), int(holdout_season), str(model)),
        ).fetchall()
        return [dict(row) for row in rows]

    # ---- helpers ---------------------------------------------------------
    @staticmethod
    def _availability_sql(
        as_of: str, required: bool, *, prefix: str = " AND ",
        table_alias: str = "",
    ) -> tuple[str, list[Any]]:
        if not required:
            return "", []
        qualifier = f"{table_alias}." if table_alias else ""
        result_available_at = f"{qualifier}result_available_at"
        received_at = f"{qualifier}received_at"
        provenance_quality = f"{qualifier}provenance_quality"
        start_time = f"{qualifier}start_time"
        placeholders = ",".join("?" * len(EVALUATION_PROVENANCE_QUALITIES))
        clause = (
            f"{result_available_at} IS NOT NULL AND {received_at} IS NOT NULL "
            f"AND {provenance_quality} IN ({placeholders}) "
            f"AND julianday({result_available_at}) IS NOT NULL "
            f"AND julianday({received_at}) IS NOT NULL "
            f"AND julianday({start_time}) IS NOT NULL "
            f"AND julianday({result_available_at}) >= julianday({start_time}) "
            f"AND julianday({received_at}) >= julianday({result_available_at}) "
            f"AND julianday({result_available_at}) < julianday(?) "
            f"AND julianday({received_at}) < julianday(?)"
        )
        return prefix + clause, [*sorted(EVALUATION_PROVENANCE_QUALITIES), as_of, as_of]

    @staticmethod
    def _feature_availability_sql(
        as_of: str, *, prefix: str = " AND ", table_alias: str = "",
        start_time_sql: str | None = None,
    ) -> tuple[str, list[Any]]:
        """SQL gate for a boxscore feature version's own arrival envelope."""
        qualifier = f"{table_alias}." if table_alias else ""
        source_available_at = f"{qualifier}source_available_at"
        received_at = f"{qualifier}received_at"
        clauses = [
            f"julianday({source_available_at}) IS NOT NULL",
            f"julianday({received_at}) IS NOT NULL",
            f"julianday({received_at}) >= julianday({source_available_at})",
            f"julianday({source_available_at}) < julianday(?)",
            f"julianday({received_at}) < julianday(?)",
        ]
        if start_time_sql:
            clauses.insert(
                2,
                f"julianday({source_available_at}) >= julianday({start_time_sql})",
            )
        return prefix + " AND ".join(clauses), [as_of, as_of]

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        if d.get("extra"):
            try:
                d["extra"] = json.loads(d["extra"])
            except Exception:  # noqa: BLE001
                pass
        return d

    def close(self) -> None:
        self.conn.close()
