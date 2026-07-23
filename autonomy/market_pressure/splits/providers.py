"""Per-source splits adapters behind one protocol.

Each provider fetches its source and parses games into ``SplitsRead``. The
parse functions are defensive -- any missing/renamed field yields fewer reads,
never an exception -- and are unit-tested against representative payloads. The
LIVE response shapes are best-effort from each site's public structure and
are marked to be confirmed the first time the tier is armed
(DUMMY_SPLITS_ENABLED=1); until then the service is inert, so an unverified
shape can do no harm.

Providers, richest first:
  * Action Network -- web JSON, carries BOTH ticket% and money%.
  * VSiN           -- DraftKings-powered ticket% + handle%.
  * Covers         -- consensus ticket% only.
  * SBR            -- consensus ticket% only.
"""
from __future__ import annotations

import re
from typing import Any, Protocol

from autonomy.market_pressure.splits.fetch import PoliteFetcher
from autonomy.market_pressure.splits.model import SplitsRead

# Our league keys -> each site's path token. Only leagues a site covers.
_AN_LEAGUE = {"mlb": "mlb", "nfl": "nfl", "nba": "nba", "nhl": "nhl",
              "ncaaf": "ncaaf", "ncaamb": "ncaab", "wnba": "wnba"}


# Nicknames whose last word is ambiguous across teams (Red Sox / White Sox)
# need the preceding word too, or two different games collide on one key.
_TWO_WORD_NICK = {"sox"}


def normalize_team(name: str | None) -> str:
    """Loose key for cross-source/venue team matching: lowercase alphanumerics,
    keep the nickname (the most stable identifier). Uses the last token, but
    the preceding one too when the last is ambiguous (redsox vs whitesox)."""
    if not name:
        return ""
    cleaned = re.sub(r"[^a-z0-9 ]", "", str(name).lower()).strip()
    if not cleaned:
        return ""
    tokens = cleaned.split()
    if len(tokens) >= 2 and tokens[-1] in _TWO_WORD_NICK:
        return tokens[-2] + tokens[-1]
    return tokens[-1]


def _pct(value: Any) -> float | None:
    """Percent or fraction -> 0..1 fraction; None on junk."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v < 0:
        return None
    return v / 100.0 if v > 1.5 else v


class SplitsProvider(Protocol):
    name: str

    def endpoint(self, sport_league: str) -> str | None:
        ...

    def parse(self, payload: Any, *, now: float) -> list[SplitsRead]:
        ...

    def fetch(self, sport_league: str, fetcher: PoliteFetcher, *, now: float) -> list[SplitsRead]:
        ...


class _JsonProvider:
    """Shared fetch for JSON sources; subclasses supply endpoint + parse."""
    name = "base"

    def endpoint(self, sport_league: str) -> str | None:  # pragma: no cover - overridden
        return None

    def parse(self, payload: Any, *, now: float) -> list[SplitsRead]:  # pragma: no cover
        return []

    def fetch(self, sport_league: str, fetcher: PoliteFetcher, *, now: float) -> list[SplitsRead]:
        url = self.endpoint(sport_league)
        if not url:
            return []
        payload = fetcher.get_json(url)
        if payload is None:
            return []
        try:
            return self.parse(payload, now=now)
        except Exception:
            return []   # fail-closed on any parse surprise


class ActionNetworkProvider(_JsonProvider):
    """Action Network web scoreboard JSON. Games carry per-side bet ("tickets")
    and money ("handle") percentages. Shape to confirm on first arming."""
    name = "action_network"

    def endpoint(self, sport_league: str) -> str | None:
        token = _AN_LEAGUE.get(sport_league)
        if not token:
            return None
        return f"https://api.actionnetwork.com/web/v2/scoreboard/{token}?period=game"

    def parse(self, payload: Any, *, now: float) -> list[SplitsRead]:
        """Parse the v2 scoreboard (confirmed live 2026-07-23).

        Real shape: each game carries ``home_team_id``/``away_team_id`` and a
        ``teams`` list (id -> full_name); splits live per-book under
        ``markets[book_id]["event"]["moneyline"]`` as a two-entry list, each
        entry tagged ``side``/``team_id`` with ``bet_info.tickets.percent`` and
        ``bet_info.money.percent``. The first book carrying complete home+away
        splits wins (they agree across books; AN publishes one split feed).
        """
        games = payload.get("games") if isinstance(payload, dict) else None
        out: list[SplitsRead] = []
        for game in games or []:
            if not isinstance(game, dict):
                continue
            names = {
                team.get("id"): team.get("full_name") or team.get("display_name")
                for team in (game.get("teams") or [])
                if isinstance(team, dict)
            }
            home = names.get(game.get("home_team_id"))
            away = names.get(game.get("away_team_id"))
            if not home or not away:
                continue
            split = self._first_complete_moneyline_split(game.get("markets"))
            if split is None:
                continue
            ht, at, hm, am = split
            if ht is not None or hm is not None:
                out.append(SplitsRead(self.name, str(home), str(away), ht, at, hm, am, now))
        return out

    @staticmethod
    def _first_complete_moneyline_split(
        markets: Any,
    ) -> tuple[float | None, float | None, float | None, float | None] | None:
        """(home_tickets, away_tickets, home_money, away_money) or None."""
        if not isinstance(markets, dict):
            return None
        for book in markets.values():
            moneyline = _dig(book, "event", "moneyline")
            if not isinstance(moneyline, list):
                continue
            by_side: dict[str, dict] = {}
            for entry in moneyline:
                if isinstance(entry, dict) and entry.get("side") in ("home", "away"):
                    by_side[str(entry["side"])] = entry.get("bet_info") or {}
            home_info, away_info = by_side.get("home"), by_side.get("away")
            if not home_info or not away_info:
                continue
            ht = _pct(_dig(home_info, "tickets", "percent"))
            at = _pct(_dig(away_info, "tickets", "percent"))
            hm = _pct(_dig(home_info, "money", "percent"))
            am = _pct(_dig(away_info, "money", "percent"))
            if ht is not None or hm is not None:
                return ht, at, hm, am
        return None


class VsinProvider(_JsonProvider):
    """VSiN betting-splits JSON (DraftKings handle% + ticket%)."""
    name = "vsin"

    def endpoint(self, sport_league: str) -> str | None:
        if sport_league not in _AN_LEAGUE:
            return None
        return f"https://data.vsin.com/api/betting-splits?sport={sport_league}&book=draftkings"

    def parse(self, payload: Any, *, now: float) -> list[SplitsRead]:
        rows = payload.get("data") if isinstance(payload, dict) else payload
        out: list[SplitsRead] = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            home, away = row.get("home_team"), row.get("away_team")
            ht = _pct(row.get("home_bets_pct") or row.get("home_tickets"))
            at = _pct(row.get("away_bets_pct") or row.get("away_tickets"))
            hm = _pct(row.get("home_handle_pct") or row.get("home_money"))
            am = _pct(row.get("away_handle_pct") or row.get("away_money"))
            if home and away and (ht is not None or hm is not None):
                out.append(SplitsRead(self.name, str(home), str(away), ht, at, hm, am, now))
        return out


class _NextDataProvider(_JsonProvider):
    """Covers / SBR embed a JSON blob (__NEXT_DATA__) in the page HTML; pull it
    out and parse the consensus (ticket%) table. Ticket-only sources."""
    name = "nextdata"
    _blob = re.compile(r'__NEXT_DATA__"[^>]*>(\{.*?\})</script>', re.DOTALL)

    def page_url(self, sport_league: str) -> str | None:  # pragma: no cover - overridden
        return None

    def rows_from_blob(self, blob: dict) -> list[dict]:  # pragma: no cover - overridden
        return []

    def fetch(self, sport_league: str, fetcher: PoliteFetcher, *, now: float) -> list[SplitsRead]:
        url = self.page_url(sport_league)
        if not url:
            return []
        html = fetcher.get_text(url)
        if not html:
            return []
        match = self._blob.search(html)
        if not match:
            return []
        try:
            import json
            blob = json.loads(match.group(1))
            return self.parse(blob, now=now)
        except Exception:
            return []

    def parse(self, payload: Any, *, now: float) -> list[SplitsRead]:
        out: list[SplitsRead] = []
        for row in self.rows_from_blob(payload if isinstance(payload, dict) else {}):
            home, away = row.get("home_team"), row.get("away_team")
            ht = _pct(row.get("home_consensus") or row.get("home_pct"))
            at = _pct(row.get("away_consensus") or row.get("away_pct"))
            if home and away and ht is not None:
                out.append(SplitsRead(self.name, str(home), str(away), ht, at, None, None, now))
        return out


class CoversProvider(_JsonProvider):
    """Covers consensus (confirmed live 2026-07-23). The __NEXT_DATA__ page was
    retired; the legacy contests table endpoint still serves a clean HTML
    consensus grid: league | away | home | date | time | away% | home% | ...
    Ticket-only source (its documented role)."""
    name = "covers"
    _row = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL)

    def page_url(self, sport_league: str) -> str | None:
        if sport_league not in _AN_LEAGUE:
            return None
        return f"https://contests.covers.com/consensus/topconsensus/{sport_league}"

    def fetch(self, sport_league: str, fetcher: PoliteFetcher, *, now: float) -> list[SplitsRead]:
        url = self.page_url(sport_league)
        if not url:
            return []
        html = fetcher.get_text(url)
        if not html:
            return []
        try:
            return self._parse_html(html, now=now)
        except Exception:
            return []

    _LEAGUE_TOKENS = frozenset({
        "MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB", "WNBA", "CFB", "CBB",
    })

    def _parse_html(self, html: str, *, now: float) -> list[SplitsRead]:
        out: list[SplitsRead] = []
        for raw in self._row.findall(html):
            text = re.sub(r"<[^>]+>", " ", raw)
            # The two consensus percentages are the first two "NN%" tokens,
            # in away-then-home order (matches the rendered grid).
            pcts = re.findall(r"(\d{1,3})\s*%", text)
            if len(pcts) < 2:
                continue
            # Team abbreviations are the two alpha tokens right after the
            # league tag in the first cell (e.g. "MLB Sd Atl").
            tokens = re.findall(r"[A-Za-z]{2,4}", text)
            teams = [
                tok for tok in tokens
                if tok.upper() not in self._LEAGUE_TOKENS
                and tok.lower() not in {"pm", "am", "et", "details", "thu", "mon",
                                        "tue", "wed", "fri", "sat", "sun", "jan",
                                        "feb", "mar", "apr", "jun", "jul", "aug",
                                        "sep", "oct", "nov", "dec", "may"}
            ]
            if len(teams) < 2:
                continue
            away, home = teams[0], teams[1]
            at = _pct(pcts[0])
            ht = _pct(pcts[1])
            if home and away and ht is not None:
                out.append(SplitsRead(self.name, home, away, ht, at, None, None, now))
        return out


class SbrProvider(_NextDataProvider):
    name = "sbr"

    def page_url(self, sport_league: str) -> str | None:
        if sport_league not in _AN_LEAGUE:
            return None
        return f"https://www.sportsbookreview.com/betting-odds/{sport_league}/consensus/"

    def rows_from_blob(self, blob: dict) -> list[dict]:
        return _dig(blob, "props", "pageProps", "consensusData") or []


def _dig(obj: Any, *keys: str) -> Any:
    """Nested-get that tolerates missing keys / non-dicts (returns None)."""
    cur = obj
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def default_providers() -> list[SplitsProvider]:
    return [ActionNetworkProvider(), VsinProvider(), CoversProvider(), SbrProvider()]
