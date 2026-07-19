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
        games = payload.get("games") if isinstance(payload, dict) else None
        out: list[SplitsRead] = []
        for game in games or []:
            if not isinstance(game, dict):
                continue
            teams = game.get("teams") or []
            home = away = None
            for team in teams:
                if not isinstance(team, dict):
                    continue
                if str(team.get("side") or team.get("home_away")).lower() in ("home", "true"):
                    home = team.get("full_name") or team.get("display_name")
                else:
                    away = team.get("full_name") or team.get("display_name")
            # Splits live under a bet_info/odds block keyed by side.
            info = game.get("bet_info") or game.get("splits") or {}
            ml = info.get("moneyline") or info.get("ml") or info
            ht = _pct(_dig(ml, "home", "tickets", "percent"))
            at = _pct(_dig(ml, "away", "tickets", "percent"))
            hm = _pct(_dig(ml, "home", "money", "percent"))
            am = _pct(_dig(ml, "away", "money", "percent"))
            if home and away and (ht is not None or hm is not None):
                out.append(SplitsRead(self.name, str(home), str(away), ht, at, hm, am, now))
        return out


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


class CoversProvider(_NextDataProvider):
    name = "covers"

    def page_url(self, sport_league: str) -> str | None:
        if sport_league not in _AN_LEAGUE:
            return None
        return f"https://www.covers.com/sport/{sport_league}/matchups?selectedConsensus=true"

    def rows_from_blob(self, blob: dict) -> list[dict]:
        return _dig(blob, "props", "pageProps", "consensus") or []


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
