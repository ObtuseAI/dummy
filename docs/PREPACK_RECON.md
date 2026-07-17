# Prepack / parlay surface recon (2026-07-17)

The Wave-10 correlation-aware parlay engine (`autonomy/parlay.py`) prices
combos but has no live market surface wired to it. This is the recon that
scopes that wire-up, taken against the public series list
(`/trade-api/v2/series?category=Sports`, 2,954 sports series).

## What exists

21 combo-family series, all football/basketball (no MLB or WNBA):

| Family | Series | Semantics |
|---|---|---|
| Cross-game ML packs | `KXNFLPREPACK2ML` `KXNFLPREPACK3ML` `KXNBAPREPACK2ML` `KXNBAPREPACK3ML` `KXNCAAFPREPACK2ML` `KXNCAAFPREPACK3ML` `KXNCAAFPREPACK4ML` `KXNCAAMB2ML` `KXMULTIPREPACK` | N moneylines across games ("2 ML Basketball Combo") |
| Same-game parlays | `KXNFLPREPACKSGP` `KXNFLPREPACKSGPSPREAD` `KXNCAAFPREPACKSGP` `KXNCAAMBSGP` | correlated legs within one game |
| Segment combos | `KXNFLPREPACK1HFT` `KXNFLPREPACK1Q1H` | half/full-time and 1Q/1H stacks |
| Misc / futures combos | `KXNFLCOMBO` `KXNFLPREPACK` `KXWCPREPACK` `KXWBCPREPACK` `KXWCGOALCOMBO` `KXMLBAWARDCOMBO` `KXWCAWARDCOMBO` | mixed; some are futures, not per-game |

## What is NOT observable yet

Every prepack series carries **zero markets at any status** (checked
unsettled/open/closed on `KXNFLPREPACK2ML` and `KXNFLPREPACKSGP`): the
2026-season shells exist but no events have been listed, and last season's
markets are purged. **Leg encoding (how a market names its component legs)
cannot be learned until the first fall listings appear (~Aug for NCAAF/NFL).**

## Staged plan (fall wave)

1. **Registry**: add the per-game combo families to `sports_markets.py` with
   `discover=False` now; flip on when the pricing path lands.
2. **Leg classifier**: on first listings, parse leg encoding from
   ticker/title/rules; each leg should resolve through the existing registry
   classifier (`classify`) so leg fair values come from the same sources that
   price the standalone markets.
3. **Pricing**: cross-game ML packs = independence product of leg fair values
   (pure vig check); SGP families = the copula engine's actual edge case —
   Wave-10 validation showed same-game stacks quote ~independence while true
   joint probability runs ~+0.12 higher on aligned 3-leg stacks.
4. **Grading**: one source per family (`prepack_ml`, `prepack_sgp`,
   `prepack_segment`), challenger-only, never auto-staked (combos multiply
   variance; staking stays human-gated).

## Why not now

The engine's edge is correlation pricing; the correlated families (SGP,
segment combos) are football/basketball only, out of season until August.
In-season effort stays on MLB/WNBA evidence accrual (Wave-12) instead.
