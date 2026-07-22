"""Conservative correlation identities for portfolio and risk controls.

Adjacent strike buckets, every surface on one sports event, and crypto assets
sharing an expiry are not independent opportunities. ``group_key`` is the
single primary cluster used by production risk caps. ``correlation_factors``
adds broader report-only factors (league-day, team/player, crypto beta and
horizon) for portfolio research without granting execution authority.
"""
from __future__ import annotations

import re

_CRYPTO_SERIES_RE = re.compile(
    r"^KX(BTC|ETH|SOL|XRP|DOGE)(15M|1H|D|W|DAILY|WEEKLY)?$"
)
_COMMODITY_RE = re.compile(r"^KX(WTI|OIL|NATGAS|NGAS|GAS|GOLD)[A-Z]*-(\d{2}[A-Z]{3}\d{2}\d{0,2})")
_WEATHER_RE = re.compile(r"^KX(HIGH|LOW|RAIN|SNOW)([A-Z]+)-(\d{2}[A-Z]{3}\d{2})")
_GAME_RE = re.compile(r"^KX([A-Z]+)GAME-(\d{2}[A-Z]{3}\d{2})(?:\d{2,4})?([A-Z]{4,10})-")
_DAY_RE = re.compile(r"^(\d{2}[A-Z]{3}\d{2})")
_SPORTS_EVENT_RE = re.compile(
    r"^\d{2}[A-Z]{3}\d{2}(?:\d{4})?([A-Z]+?)(?:G\d)?$"
)

_ASSET_CANON = {"OIL": "WTI", "NGAS": "NATGAS", "GAS": "NATGAS"}


def _sports_spec(ticker: str):
    """Return the canonical sports series spec without creating an import cycle."""
    try:
        from autonomy.sports_markets import spec_for

        return spec_for(ticker)
    except (ImportError, AttributeError):
        return None


def _crypto_identity(ticker: str) -> tuple[str, str, str] | None:
    parts = ticker.split("-")
    if len(parts) < 2:
        return None
    match = _CRYPTO_SERIES_RE.match(parts[0])
    if match is None:
        return None
    asset, raw_horizon = match.groups()
    horizon = {
        None: "LADDER",
        "D": "DAILY",
        "W": "WEEKLY",
    }.get(raw_horizon, raw_horizon)
    return asset, str(horizon), parts[1]


def _subject_team(token: str, teams_blob: str) -> str | None:
    """Best-effort team prefix from a team/player contract token.

    Prop tokens are ``TEAM + abbreviated-player + id``. Choosing the longest
    2-5 character prefix that also occurs in the event team blob is deliberately
    conservative: a parse miss simply omits the broader team factor while the
    exact event cap still applies.
    """
    letters = re.match(r"^[A-Z]+", token)
    if letters is None:
        return None
    prefixable = letters.group(0)
    for length in range(min(5, len(prefixable)), 1, -1):
        candidate = prefixable[:length]
        if candidate in teams_blob:
            return candidate
    return None


def group_key(ticker: str) -> str:
    """Return the correlated-cluster id for a market ticker."""
    t = ticker.upper()

    crypto = _crypto_identity(t)
    if crypto is not None:
        asset, horizon, expiry = crypto
        return f"CRYPTO:{asset}:{horizon}:{expiry}"

    # The canonical registry covers winner/spread/total/segment/team-total and
    # player-prop series. Their second token is the shared event identity, so
    # every surface of one matchup must consume the same production risk cap.
    spec = _sports_spec(t)
    parts = t.split("-")
    if spec is not None and len(parts) >= 2:
        return f"SPORTS:{spec.league.upper()}:{parts[1]}"

    m = _COMMODITY_RE.match(t)
    if m:
        asset = _ASSET_CANON.get(m.group(1), m.group(1))
        return f"COMMODITY:{asset}:{m.group(2)}"

    m = _WEATHER_RE.match(t)
    if m:
        return f"WX:{m.group(2)}:{m.group(3)}"

    m = _GAME_RE.match(t)
    if m:
        # Sort the concatenated team codes so both market sides share a key.
        return f"GAME:{m.group(1)}:{m.group(2)}:{''.join(sorted(m.group(3)))}"

    # Fallback: the event stem (everything before the last dash segment).
    parts = t.rsplit("-", 1)
    return f"EVENT:{parts[0]}" if len(parts) == 2 else f"EVENT:{t}"


def correlation_factors(ticker: str) -> tuple[str, ...]:
    """Return deterministic nested concentration factors for portfolio research.

    The first factor is always ``group_key(ticker)``. Additional factors are
    broader and intentionally conservative. They are consumed by the
    report-only portfolio challenger; production order sizing still uses only
    the primary group and therefore cannot gain capital authority here.
    """
    t = str(ticker).upper()
    factors = [group_key(t)]
    parts = t.split("-")

    crypto = _crypto_identity(t)
    if crypto is not None:
        asset, horizon, expiry = crypto
        # Same expiry across BTC/ETH/SOL/etc. shares the broad crypto-beta shock.
        factors.append(f"FACTOR:CRYPTO:BETA_EXPIRY:{horizon}:{expiry}")
        day_match = _DAY_RE.match(expiry)
        if day_match:
            day = day_match.group(1)
            factors.extend((
                f"FACTOR:CRYPTO:BETA_DAY:{horizon}:{day}",
                f"FACTOR:CRYPTO:ASSET_DAY:{asset}:{day}",
            ))
        return tuple(dict.fromkeys(factors))

    spec = _sports_spec(t)
    if spec is not None and len(parts) >= 2:
        event = parts[1]
        day_match = _DAY_RE.match(event)
        day = day_match.group(1) if day_match else "UNKNOWN_DAY"
        factors.append(f"FACTOR:SPORTS:LEAGUE_DAY:{spec.league.upper()}:{day}")

        event_match = _SPORTS_EVENT_RE.match(event)
        teams_blob = event_match.group(1) if event_match else ""
        if len(parts) >= 3 and teams_blob:
            subject_token = parts[-2] if spec.is_prop and len(parts) >= 4 else parts[-1]
            team = _subject_team(subject_token, teams_blob)
            if team:
                factors.append(
                    f"FACTOR:SPORTS:TEAM_DAY:{spec.league.upper()}:{day}:{team}"
                )
                if spec.is_prop:
                    player = re.sub(r"\d+$", "", subject_token[len(team):])
                    if player:
                        factors.append(
                            f"FACTOR:SPORTS:PLAYER_DAY:{spec.league.upper()}:{day}:{player}"
                        )
        return tuple(dict.fromkeys(factors))

    return tuple(dict.fromkeys(factors))
