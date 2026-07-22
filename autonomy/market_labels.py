"""Human-readable labels for Kalshi market tickers (dashboard readability).

Turns raw tickers -- ``KXMLBRFI-26JUL211915SDATL``,
``KXWNBA2HTOTAL-26JUL19CONNPHX-76`` -- into ``SD vs ATL · 1st-inning run`` /
``CONN vs PHX · 2H total 76``, so the board never shows a wall of ticker codes.

Team codes are concatenated with no delimiter in the event token, so they are
split with per-league abbreviation sets learned from the history lake (greedy
longest-valid split), with a graceful fallback to the raw token when no clean
split is found. Pure-Python, cached, fail-soft: any parse miss returns the raw
ticker rather than raising.
"""
from __future__ import annotations

import re
from datetime import date as calendar_date
from functools import lru_cache
from typing import Any

from autonomy.sports_markets import (
    F3, F5, F7, H1, H2, Q1, Q2, Q3, Q4, PROP, SPREAD, TEAM_TOTAL, TOTAL,
    WINNER, YRFI, spec_for,
)

_MON = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
_MON_TITLE = {m: m.title() for m in _MON}
# YY MON DD [HHMM] TEAMS [G<n> doubleheader]
_EVENT_RE = re.compile(r"^(\d{2})([A-Z]{3})(\d{2})(\d{4})?([A-Z].*?)(G\d)?$")

_SEGMENT = {H1: "1H", H2: "2H", Q1: "1Q", Q2: "2Q", Q3: "3Q", Q4: "4Q",
            F3: "1st 3", F5: "1st 5", F7: "1st 7"}
_MARKET = {WINNER: "winner", SPREAD: "spread", TOTAL: "total",
           TEAM_TOTAL: "team total", YRFI: "1st-inning run", PROP: "prop"}

# Tokens that appear in the team slot but are not real matchup teams (all-star /
# exhibition / conference placeholders); excluded from the split vocabulary so
# they can't cause a mis-split of a real game.
_NON_TEAM = {"AL", "NL", "ALL", "ALLSTAR", "EAST", "WEST", "USA", "WORLD",
             "TBD", "STARS", "WNBASTARS", "PUERTORICO", "NIGER", "PAR", "DEL",
             "STE", "WIL", "GIA", "DUR", "LEB"}

# Kalshi abbreviations that differ from the lake's ESPN codes -- added to the
# split vocabulary so a real game still resolves (displayed as the Kalshi code).
_EXTRA_TEAMS = {
    "mlb": {"AZ", "CWS", "SFG", "TBR", "KCR", "SDP", "CHW", "WSH", "ATH"},
    "nfl": {"JAC", "WSH", "LAR", "LV"},
    "nba": {"NOP", "NYK", "GSW", "SAS", "UTA", "WSH", "PHO"},
    "wnba": {"CONN", "PHX", "NYL", "LVA", "GSV"},
    "nhl": {"TBL", "LAK", "SJS", "NJD", "VGK", "WSH", "MTL"},
}


@lru_cache(maxsize=1)
def _team_sets() -> dict[str, frozenset[str]]:
    """``{league: {ABBR, ...}}`` learned from the history lake; empty on any miss.

    Read-only, never creates or migrates the lake -- a missing lake just means
    labels fall back to the raw team token.
    """
    import sqlite3

    from autonomy.sports.history_store import DEFAULT_PATH

    try:
        conn = sqlite3.connect(f"file:{DEFAULT_PATH}?mode=ro", uri=True)
        try:
            rows = conn.execute("SELECT DISTINCT league, home, away FROM games").fetchall()
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 -- no lake yet => humanize falls back to raw
        return {}
    out: dict[str, set[str]] = {}
    for league, home, away in rows:
        s = out.setdefault(str(league).lower(), set())
        for t in (home, away):
            t = str(t).upper().strip()
            if t and t not in _NON_TEAM:
                s.add(t)
    for lg, extra in _EXTRA_TEAMS.items():
        out.setdefault(lg, set()).update(extra)
    return {lg: frozenset(v) for lg, v in out.items()}


def _split_teams(blob: str, league: str) -> tuple[str, str] | None:
    """Greedy longest-valid split of a concatenated team token (SDATL -> SD, ATL)."""
    tset = _team_sets().get(league)
    if not tset or len(blob) < 4:
        return None
    # Prefer the split whose FIRST team is longest (real abbrevs beat spurious
    # short prefixes), requiring both halves to be known teams.
    for i in range(len(blob) - 1, 1, -1):
        if blob[:i] in tset and blob[i:] in tset:
            return blob[:i], blob[i:]
    return None


def _event_parts(ticker: str) -> tuple[str | None, str | None, str | None]:
    """(teams_blob, 'Mon DD', YYYY-MM-DD) from the sports event token."""
    parts = str(ticker).split("-")
    if len(parts) < 2:
        return None, None, None
    m = _EVENT_RE.match(parts[1])
    if not m:
        return None, None, None
    yy, mon, dd, _hhmm, blob, _dh = m.groups()
    date = f"{_MON_TITLE.get(mon, mon.title())} {int(dd)}" if mon in _MON_TITLE else None
    event_date = None
    if mon in _MON:
        try:
            event_date = calendar_date(2000 + int(yy), _MON.index(mon) + 1, int(dd)).isoformat()
        except ValueError:
            pass
    return (blob or None), date, event_date


def _line_or_subject(ticker: str) -> tuple[str | None, str | None]:
    """(subject_team, line) from the trailing token; either may be None.

    Winner/spread/team_total carry a subject team (``-NYY``, ``-BOS11``); totals
    carry a numeric line (``-76``, ``-3``). A leading ``T`` strike (crypto) is
    treated as a line.
    """
    parts = str(ticker).split("-")
    if len(parts) < 3:
        return None, None
    tail = parts[-1]
    if tail.upper() == "TIE":
        return "tie", None
    mline = re.match(r"^([A-Z]+?)(\d+(?:\.\d+)?)?$", tail)
    if mline and mline.group(1) and mline.group(1) != "T":
        return mline.group(1), (mline.group(2) or None)
    mnum = re.match(r"^T?(\d+(?:\.\d+)?)$", tail)
    if mnum:
        return None, mnum.group(1)
    return None, None


def _ticker_player_abbreviation(token: str, team: str | None) -> str | None:
    """Return the player identity encoded in a Kalshi prop token.

    Player tokens have the shape ``TEAM + first initial + surname + number``
    (for example ``NYMFLINDOR12``). The market title remains the authoritative
    full name; this parser is the loss-minimizing fallback for ledger rows that
    predate title persistence. It never invents a first name.
    """
    if not team:
        return None
    normalized = str(token or "").upper()
    prefix = str(team).upper()
    if not normalized.startswith(prefix):
        return None
    encoded = normalized[len(prefix):]
    match = re.fullmatch(r"([A-Z])([A-Z]{2,})(\d+)", encoded)
    if not match:
        return None
    surname = match.group(2)
    display_surname = {
        "CROWARMSTRONG": "Crow-Armstrong",
        "DELACRUZ": "De La Cruz",
    }.get(surname, surname.title())
    return f"{match.group(1)} {display_surname}"


def humanize_ticker(ticker: str) -> dict[str, Any]:
    """Readable pieces for a ticker: ``{matchup, market, line, date, label}``.

    Always returns a dict; unparseable tickers fall back to the raw string so a
    label is never blank. ``label`` is the one-line display string.
    """
    raw = str(ticker)
    spec = spec_for(raw)
    blob, date, event_date = _event_parts(raw)
    event_id = raw.split("-", 2)[1] if spec is not None and "-" in raw else None
    subject, line = _line_or_subject(raw)

    matchup = None
    if blob:
        league = spec.league if spec else ""
        pair = _split_teams(blob, league)
        matchup = f"{pair[0]} vs {pair[1]}" if pair else blob

    # market phrase
    market = None
    if spec is not None:
        seg = _SEGMENT.get(spec.segment)
        base = spec.stat if (spec.market_type == PROP and spec.stat) else _MARKET.get(spec.market_type, spec.market_type)
        market = f"{seg} {base}" if seg else base
        if spec.market_type in (WINNER, TEAM_TOTAL) and subject and subject != "tie":
            market = f"{market} ({subject})"
        elif subject == "tie":
            market = f"{market} (tie)"
        if line and spec.market_type in (TOTAL, TEAM_TOTAL, SPREAD):
            market = f"{market} {line}"

    if matchup and market:
        label = f"{matchup} · {market}"
    elif matchup:
        label = matchup
    elif market:
        label = market
    else:
        label = raw
    return {
        "matchup": matchup or raw,
        "market": market,
        "subject": subject,
        "line": line,
        "date": date,
        "event_date": event_date,
        "event_id": event_id,
        "label": label,
    }


def humanize_market(ticker: str, title: str | None = None) -> dict[str, Any]:
    """Return display pieces enriched with a prop's player or team subject.

    Kalshi player-prop tickers abbreviate the player token, while the market
    title carries the reliable display name (``"Yandy Diaz: 2+ hits?"``).  The
    live cycle therefore uses the title.  A cold-start ledger row has no title,
    so it falls back to the team encoded in the prop token rather than showing
    an anonymous ``"hits"`` or ``"strikeouts"`` row.
    """
    pieces = dict(humanize_ticker(ticker))
    pieces["subject_team"] = pieces.get("subject")
    spec = spec_for(str(ticker))
    if spec is None or spec.market_type != PROP:
        return pieces

    raw_title = str(title or "").strip()
    title_match = re.match(r"^\s*(.+?)\s*:\s*(.+?)\s*\??\s*$", raw_title)
    player = title_match.group(1).strip() if title_match else None
    description = title_match.group(2).strip() if title_match else None

    # Prop tickers are ``series-event-TEAMPLAYERID-line``. On ledger fallback
    # the title is unavailable, but the token still carries an exact first
    # initial plus surname. Use that non-fabricated abbreviation before the
    # older team-level fallback.
    subject_team = None
    parts = str(ticker).upper().split("-")
    token = parts[-2] if len(parts) >= 4 else ""
    matchup_teams = str(pieces.get("matchup") or "").split(" vs ")
    for team in sorted((t for t in matchup_teams if t), key=len, reverse=True):
        if token.startswith(team.upper()):
            subject_team = team
            break

    ticker_player = _ticker_player_abbreviation(token, subject_team)
    subject = player or ticker_player or (
        f"{subject_team} player" if subject_team else "Player"
    )
    if not description:
        stat = str(spec.stat or "prop").replace("_", " ")
        line = pieces.get("line")
        description = f"{line}+ {stat}" if line else stat
    display_market = f"{subject} · {description.rstrip('?').strip()}"
    matchup = pieces.get("matchup")
    pieces.update({
        "subject": subject,
        "subject_team": subject_team,
        "market": display_market,
        "label": f"{matchup} · {display_market}" if matchup else display_market,
    })
    return pieces


def market_label(ticker: str) -> str:
    """The one-line readable label (convenience wrapper)."""
    return humanize_ticker(ticker)["label"]
