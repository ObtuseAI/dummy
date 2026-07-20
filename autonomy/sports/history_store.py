"""Phase 1: the sports historical data lake — a point-in-time store.

A persistent, multi-season SQLite store of free/public sports data (game
results + boxscores + play-by-play + odds lines + injuries), the foundation the
analytics foundry and the walk-forward backtester read from. Every row carries
``as_of`` + ``source`` + ``provenance_url`` so a query can reconstruct exactly
what was known at any past instant.

Point-in-time is the whole point: :meth:`games_before` and :meth:`team_form`
return only games that had already **finished** strictly before the given
instant, so a model's cold-start prior or a walk-forward replay can never see a
result that hadn't happened yet. Pure stdlib (sqlite3 + json), house style:
no numpy/pandas. Own DB file (never the ledger), with its own retention.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

DEFAULT_PATH = Path("runtime/autonomy/sports_history.db")

# A game is "complete" (safe to read as history) only in these statuses.
_FINAL_STATUSES = ("final", "post", "closed", "complete", "completed")


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
                extra TEXT
            );
            CREATE INDEX IF NOT EXISTS ix_games_league_time ON games(league, start_time);
            CREATE INDEX IF NOT EXISTS ix_games_season ON games(league, season);

            CREATE TABLE IF NOT EXISTS boxscores(
                game_id TEXT NOT NULL, team TEXT NOT NULL, player TEXT,
                stat TEXT NOT NULL, value REAL,
                as_of TEXT, source TEXT,
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
                g.get("as_of") or g.get("start_time"), g.get("source"), g.get("provenance_url"),
                json.dumps(g.get("extra")) if g.get("extra") is not None else None,
            )
            for g in games
        ]
        self.conn.executemany(
            """INSERT INTO games(game_id,league,season,start_time,status,home,away,
                   home_score,away_score,venue,neutral,as_of,source,provenance_url,extra)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(game_id) DO UPDATE SET
                   season=excluded.season, start_time=excluded.start_time,
                   status=excluded.status, home=excluded.home, away=excluded.away,
                   home_score=excluded.home_score, away_score=excluded.away_score,
                   venue=excluded.venue, neutral=excluded.neutral,
                   as_of=excluded.as_of, source=excluded.source,
                   provenance_url=excluded.provenance_url, extra=excluded.extra""",
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
        """Upsert team-level boxscores. Each row: {game_id, team, stats:{k:v}}."""
        tuples = [
            (r["game_id"], r["team"], "", stat, float(val),
             r.get("as_of"), r.get("source", "espn"))
            for r in rows
            for stat, val in (r.get("stats") or {}).items()
        ]
        if not tuples:
            return 0
        self.conn.executemany(
            """INSERT INTO boxscores(game_id,team,player,stat,value,as_of,source)
               VALUES(?,?,?,?,?,?,?)
               ON CONFLICT(game_id,team,player,stat) DO UPDATE SET
                   value=excluded.value, as_of=excluded.as_of, source=excluded.source""",
            tuples,
        )
        self.conn.commit()
        return len(tuples)

    def game_ids_missing_boxscores(self, league: str, limit: int | None = None) -> list[str]:
        """Completed game_ids in ``league`` that have no boxscore rows yet
        (newest first) -- the resumable work-list for the boxscore backfill."""
        finals = ",".join("?" * len(_FINAL_STATUSES))
        sql = (
            f"SELECT g.game_id FROM games g LEFT JOIN boxscores b ON b.game_id = g.game_id "
            f"WHERE g.league = ? AND g.status IN ({finals}) AND b.game_id IS NULL "
            f"GROUP BY g.game_id ORDER BY g.start_time DESC"
        )
        params: list[Any] = [league, *_FINAL_STATUSES]
        if limit:
            sql += " LIMIT ?"
            params.append(int(limit))
        return [r[0] for r in self.conn.execute(sql, params).fetchall()]

    def team_stat_sums_before(
        self, team: str, as_of: str, league: str,
    ) -> dict[str, Any] | None:
        """Point-in-time SUM of a team's OWN boxscore stats over completed games
        before ``as_of`` (any stat keys). ``{"sums": {...}, "games": n}`` or
        None. Used where a team's row already encodes both sides (e.g. EPA)."""
        finals = ",".join("?" * len(_FINAL_STATUSES))
        gids = [
            r[0] for r in self.conn.execute(
                f"""SELECT DISTINCT g.game_id FROM games g
                    JOIN boxscores b ON b.game_id = g.game_id
                    WHERE b.team = ? AND b.player = '' AND g.league = ?
                      AND g.start_time < ? AND g.status IN ({finals})""",
                (team, league, as_of, *_FINAL_STATUSES),
            ).fetchall()
        ]
        if not gids:
            return None
        ph = ",".join("?" * len(gids))
        sums = {s: v for s, v in self.conn.execute(
            f"SELECT stat, SUM(value) FROM boxscores WHERE game_id IN ({ph}) AND team = ? "
            f"AND player = '' GROUP BY stat", (*gids, team)).fetchall()}
        return {"sums": sums, "games": len(gids)}

    def four_factor_sums_before(
        self, team: str, as_of: str, league: str,
    ) -> dict[str, Any] | None:
        """Point-in-time stat sums for a team's OFFENSE (own) and DEFENSE
        (opponents' stats in the same games), over completed games before
        ``as_of``. The seed for four-factors. None if no boxscores yet."""
        finals = ",".join("?" * len(_FINAL_STATUSES))
        gids = [
            r[0] for r in self.conn.execute(
                f"""SELECT DISTINCT g.game_id FROM games g
                    JOIN boxscores b ON b.game_id = g.game_id
                    WHERE b.team = ? AND b.player = '' AND g.league = ?
                      AND g.start_time < ? AND g.status IN ({finals})""",
                (team, league, as_of, *_FINAL_STATUSES),
            ).fetchall()
        ]
        if not gids:
            return None
        ph = ",".join("?" * len(gids))
        own = {s: v for s, v in self.conn.execute(
            f"SELECT stat, SUM(value) FROM boxscores WHERE game_id IN ({ph}) AND team = ? "
            f"AND player = '' GROUP BY stat", (*gids, team)).fetchall()}
        opp = {s: v for s, v in self.conn.execute(
            f"SELECT stat, SUM(value) FROM boxscores WHERE game_id IN ({ph}) AND team != ? "
            f"AND player = '' GROUP BY stat", (*gids, team)).fetchall()}
        return {"off": own, "def": opp, "games": len(gids)}

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
        self, as_of: str, league: str | None = None, season: int | None = None,
    ) -> list[dict[str, Any]]:
        """Completed games that started strictly before ``as_of`` (most recent
        first). Never returns a scheduled/in-progress game — no future leakage."""
        clause = ["start_time < ?", "status IN (%s)" % ",".join("?" * len(_FINAL_STATUSES))]
        params: list[Any] = [as_of, *_FINAL_STATUSES]
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
        self, team: str, as_of: str, league: str | None = None, n: int = 20,
    ) -> list[dict[str, Any]]:
        """The team's last ``n`` completed games before ``as_of`` (most recent
        first) — the point-in-time information set for a cold-start prior."""
        params: list[Any] = [as_of, *_FINAL_STATUSES, team, team]
        clause = "start_time < ? AND status IN (%s) AND (home = ? OR away = ?)" % (
            ",".join("?" * len(_FINAL_STATUSES))
        )
        if league is not None:
            clause += " AND league = ?"
            params.append(league)
        rows = self.conn.execute(
            "SELECT * FROM games WHERE " + clause + " ORDER BY start_time DESC LIMIT ?",
            [*params, int(n)],
        ).fetchall()
        return [self._row(r) for r in rows]

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

    # ---- helpers ---------------------------------------------------------
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
