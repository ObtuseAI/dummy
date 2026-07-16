# Player-prop lines (Wave-3, fixtures-first, governance-gated)

`autonomy/player_props.py` adds plumbing for player-prop over/under lines
(hits, total bases, …). It parses the licensed odds payload shape (The Odds API
v4 event-odds, `markets` = `player_*`), pairs each book's Over/Under for the
same `(player, point)`, de-vigs it to a fair `P(over)` via `devig_two_way`, and
averages across books. It is **challenger evidence only** and cannot reach
execution.

## Fail-closed parsing

Every ambiguity is dropped, never guessed:

- a one-sided quote (Over with no matching Under, or vice-versa),
- an Over and Under whose `point` differs,
- a malformed row (missing player, non-numeric price/point),
- a malformed or empty payload.

See `tests/fixtures/player_props_onesided.json` — it yields **zero** quotes.

## The governance slot

Player-prop data comes from the **same** licensed, key-based aggregator as
`autonomy/odds_providers.py`, so it reuses that module's disabled-by-default
slot and its two environment switches:

| env var | meaning | default |
|---|---|---|
| `DUMMY_ODDS_API_KEY` | licensed API key | unset |
| `DUMMY_ODDS_API_ENABLED` | `"1"` to arm, **after** source-universe review + ToS acceptance | unset |

`LicensedPropProvider.available` is `True` only when **both** are set. With the
slot closed it never touches the network and returns nothing — there is no live
path that bypasses the key. `FixturePropProvider` reads only committed sample
fixtures and contacts no provider, so the parser/de-vig are fully testable
offline.

Until the operator opens the slot, the challenger (`prop_over_probability`) is
**dormant-but-ready**: it always returns `None` for the licensed provider, the
same posture as the Wave-2 cross-venue econ source. Opening it is an operator
decision, not a code change here.

No site that forbids automated access is scraped; the module speaks only to an
API the operator has licensed.
