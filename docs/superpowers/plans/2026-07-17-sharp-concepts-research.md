# Sharp-Concepts Research Program: what elite traders/bettors do, translated and sharpened

**Operator directive (2026-07-17, Chris):** experiment with patience/confirmation
on crypto 15m+hourly; invent weighted adaptive indicators; research what the
best traders and bettors do and make those concepts better.

Every concept below is translated to Kalshi binaries, mapped to what dummy
already has, and — where new — preregistered with a falsification condition
BEFORE any evidence accrues (Wave-7 discipline; see
`scripts/preregister_wave8.py`). Nothing enters fusion except through the
WS-14 ladder.

## Shipped in Wave-8

| Concept (source tradition) | Translation | Status |
|---|---|---|
| Patience / "don't bet every race" + late-market sharpness (racing/sports sharps: closing markets are sharpest, and the last information beats the first opinion) | `CryptoPatienceSignal`: speak only in the final 40% of a 15m/hourly window AND after spot confirms toward the reference. **Our own battery motivated it**: always-on crypto sources showed ~zero row discrimination — the early window is noise. | LIVE (challenger) |
| Adaptive position of trend followers (Kaufman; turtle-style "let the regime size the signal") | `CryptoKamaMomentumSignal`: drift weighted by the efficiency ratio — trend speaks, chop auto-converges to no-drift. The weighting is the indicator. | LIVE (challenger) |

## The concept map — where dummy already embodies sharp practice

- **CLV as ground truth** (sports bettors' north star) → sports CLV recorder + ladder criterion. ✔
- **Independent price first, market second** (advantage players) → every source is graded contested-only vs `market_prior`. ✔
- **Fractional Kelly under uncertainty** → risk brain staging + uncertainty-aware envelopes. ✔
- **Specialize; refuse bad games** → per-scope champions, abstention-first, no-edge map. ✔
- **Steam detection** (originators vs followers) → sportsbook steam signal (sports). ✔ *Gap: crypto analog below.*
- **Bet the number, not the team** (line-value discipline) → strike-ladder lattice coherence. ✔
- **Complete records, no memory-grading** → immutable ledger + provenance. ✔

## Preregistered backlog (build order)

1. **Spot-lead latency origination** (`crypto_spot_lead_latency`) — the crypto
   steam-origination analog: fresh spot moved, Kalshi book hasn't repriced →
   take the stale side. Needs: intra-cycle fresh-spot read beside the
   `live_book` WebSocket quote (both exist; wire a book-timestamp vs spot-
   timestamp comparator). Highest expected row-level discrimination of the
   backlog — it is *mechanically* information the book lacks.
2. **Kalshi order-flow imbalance** (`kalshi_book_imbalance_ofi`) — depth-delta
   footprint from the WS feed as a direction feature. Microstructure classic
   (Cont et al.), untested on binary books — exactly the kind of thing the
   preregistration + battery machinery exists to adjudicate.
3. **Strike pin/magnet near expiry** (`crypto_strike_pin_magnet`) — options
   pin-risk folklore, measurable here because strikes and expiries are dense.
4. **Middles/ladder scalps** — when adjacent-strike prices violate the joint
   distribution by more than fees, the lattice already detects it; add an
   execution-policy cohort that takes both sides (risk-free-band capture).
5. **Time-of-day participant mix** — retail-heavy hours (US evening) vs
   funding-window hours (00/08/16 UTC): condition existing signals' trust by
   session bucket via the scoped-trust machinery (no new source needed —
   extend `horizon_or_phase` with a session axis, evidence first).

## Making the concepts *better* than the tradition

The sharp traditions run on human discipline; dummy's upgrades are structural:

- Sharps *feel* when their edge decays — dummy auto-demotes on trailing CI and
  runs a standing negative-control battery no human bettor has.
- Sharps track CLV in spreadsheets — dummy's CLV is per-scope, cluster-robust,
  and wired into promotion criteria.
- Sharps cap exposure by instinct — the conservative-advantage stack
  (CI x Sidak x correlation) is instinct made auditable.
- Sharps specialize by market — the taxonomy makes specialization the default
  unit of evidence, not an aspiration.

## Standing rules for this program

Challenger-only; fail-closed; preregister before evidence; battery before
belief; the no-edge map is a valid and celebrated outcome for any concept
that dies. Fees and the taker EV gate are part of every economic claim.
