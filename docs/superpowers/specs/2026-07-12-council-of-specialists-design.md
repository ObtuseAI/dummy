# Council of Specialists — Master Architecture Design

**Date:** 2026-07-12
**Status:** Approved (operator directive: "design it even more innovative and novel… every sports league and crypto should have its own subagent… greatest architecture… second to none. we will be removing ufc and f1")
**Decisions locked:** in-process council (one loop, per-specialist cadence budgets — NOT one OS process per league), season-driven phase order, challenger-only + fail-closed everywhere, UFC/F1 retired.

---

## 1. Vision

Transform dummy from *one brain with many signals* into a **council of specialist subagents** — one per league (MLB, NFL, NBA, NHL, NCAAF, NCAAMB) plus crypto — each owning its vertical end-to-end (model, live re-pricing, sharp book, injuries/availability, persistence, health), all reporting through a uniform protocol to a **central core that keeps sole capital authority**.

**Safety invariant (non-negotiable):** specialists forecast; the core decides. No specialist ever touches allocator / executor / risk brain. Everything new ships `challenger_only`, is graded per-market-type by contested Brier (and CLV, §3.2), and fails closed at every feed: missing data → abstain → byte-identical forecasts.

Verified 2026-07-12 against the live Kalshi API: **every league has winner + total + spread series** — `KXNFLGAME/TOTAL/SPREAD`, `KXNBAGAME/TOTAL/SPREAD`, `KXNHLGAME/TOTAL/SPREAD`, `KXNCAAFGAME/TOTAL/SPREAD`, `KXNCAAMBGAME/TOTAL/SPREAD` all return 200.

## 2. The Specialist Protocol

New package `autonomy/specialists/`. Uniform interface:

```python
class Specialist(Protocol):
    name: str                                    # "mlb", "nfl", "crypto", ...
    def applicable(self, market) -> bool         # ticker-routed, disjoint by series prefix
    def forecast(self, market) -> Signal | None  # pre-game model view
    def live_forecast(self, market) -> Signal | None  # in-play view (None = abstain)
    def book(self, market) -> float | None       # de-vigged independent sharp estimator
    def on_cycle_start(self) -> None             # warm caches, refresh feeds (bounded)
    def health(self) -> SpecialistHealth         # freshness, model age, settled n, Brier, CLV
```

- `SpecialistRegistry` routes each market to exactly one specialist (series prefixes are disjoint — verified).
- The existing `SourceRegistry`/signal machinery **stays**. Specialists *wrap* shipped signals (MLB intelligence, crypto stack, sports Elo, sportsbook consensus) rather than rewrite them — Phase 0 migration is zero-behavior-change by construction.
- **In-process council.** One monitor loop iterates specialists with per-specialist cadence budgets. Rationale: 4 schtasks already produced observed SQLite contention (110s+ API hangs during screenshot capture); 7 more OS processes would strangle the DB. In-process gives the same isolation (per-specialist state, fail-closed boundaries) without the contention.
- `run_dummy_mispricing_monitor.py::_build()` collapses from hand-wired MLB closures to "ask the registry": `forecast_fn`/`book_fn` become registry dispatches.

## 3. Cross-cutting novel layers (the "second to none" edge)

### 3.0 The 3x3 conviction lattice (operator directive, 2026-07-12)
Every game, every sport, gets a nine-cell lattice: **three estimators**
(our sport-native model, the de-vigged sharp book, the Kalshi crowd) **x
three market families** (winner, spread ladder, total ladder). Triangulation
ties the lattice vertically (model+book vs Kalshi per family, section 3.1's
predecessor engine); coherence ties it horizontally (one joint score
distribution must price all three families consistently, section 3.1).
**Cross-cell confirmation is the top conviction tier:** an edge visible in
the winner cell whose direction is independently implied by the spread-
ladder cells, with book agreement in both, is the strongest signal the
system can emit. Each sport fills its lattice natively -- key-number kernel
cells (NFL/NCAAF), Skellam+OT cells (NHL), heteroskedastic pace cells
(NBA/NCAAMB), PA-sim cells (MLB), DVOL-implied strike-ladder cells (crypto,
where the "families" are the threshold/range/direction contract shapes).
Custom-tailored per sport, one shared conviction algebra.

### 3.1 Cross-market coherence engine (`autonomy/coherence.py`)
Each specialist prices winner + spread + total for a game from **one joint score distribution**. Kalshi prices them as three independent markets set by three independent crowds. When Kalshi's spread price implies a win probability inconsistent with its own winner market (beyond fees/spread), that is a **structural incoherence** — an edge requiring no model opinion, only internal-consistency math. Feeds the opportunist as a confidence tier **above** `model+book`. Seeded on MLB (live now), inherited free by every later specialist because the protocol already demands joint pricing.

### 3.2 CLV grading (closing-line-value)
Settlements are slow, noisy feedback. The sharp book's **closing line** is the industry-standard truth proxy converging ~10× faster. Grade every paper strike and shortlist entry against the de-vigged close: `clv_bps` per decision, aggregated per (specialist, market_type). The retro engine learns from CLV *and* settlements; a specialist that consistently beats the close surfaces promotion evidence weeks earlier. CLV is evidence for review — settlement-backed contested Brier remains the promotion gate.

### 3.3 Regime-conditional trust surface
Extend contested-Brier keying from (source, market_type) to **(specialist, market_type, phase)**, phase ∈ {pre, live}. A specialist can be sharp pre-game and noise live, or vice versa. Trust is a surface, not a scalar. Bounded dimensionality on purpose (no unbounded regime taxonomy).

### 3.4 Propose-then-promote self-tuning
Nightly walk-forward re-fit of each specialist's calibration constants (sigmas, shrinkage-toward-market λ) on settled history → written as a **proposal artifact** with before/after Brier deltas. Never self-applies. Promotion is an explicit governance action once contested evidence clears. Recursive self-improvement with fail-closed DNA.

## 4. MLB specialist — review findings (Phase 2)

Shipped stack (PA sim, L/R splits, bullpen, rivalry/divisional, weather, injuries, live winner/total/spread, DVOL-style book via ESPN pickcenter, opportunist) is deep. Gaps found:

1. **Park factors** — run/HR environment varies ~20% Coors-to-Oracle. Static auditable table scaling expected runs. Cheap, high-value for totals.
2. **Live base-out state** — live model uses only score + inning; ESPN summary `plays` carries runners/outs. Bases-loaded-nobody-out ≠ empty-two-out. Feeds the shipped PA sim's situational machinery.
3. **Times-through-order / starter fatigue decay** in live totals (3rd time through the order is a known scoring inflection).
4. **Rest/travel** — day-game-after-night, b2b road series; computable from ESPN schedule already fetched.
5. **CLV grading** (§3.2) and **coherence engine** (§3.1) land here first — MLB is mid-season, live validation runway now.

## 5. New league specialists — true scoring processes, not a shared normal

Current generic tier (`autonomy/sports/team_scores.py`): EWMA points-for/against + fixed-sigma normal margin/total. Replaced per league:

### 5.1 NFL
- **Shifted empirical margin kernel.** NFL margins are NOT normal — probability mass spikes at 3, 7, 10. Team-strength EWMA/Elo → mean margin → historical NFL margin pmf re-centered on that mean → winner/spread/total priced **jointly and coherently**, key numbers priced correctly. (A normal model misprices −2.5/−3.5 spreads badly; that's where the edge lives.)
- **QB status special-case** — the one injury that moves lines 5+ points; ESPN depth chart + injuries feed.
- Rest asymmetry: bye weeks, Thursday short weeks.
- **Outdoor weather via existing Open-Meteo pipeline** (wind/temp → totals; reuses the weather→sports pivot).
- Live: drive-state model (possession, field position, clock) from ESPN summary.

### 5.2 NBA
- **Pace × efficiency decomposition** — possessions/game and points/possession EWMAs per team; total mean from pace-matched product; **sigma scales with pace** (heteroskedastic, replaces fixed 15.0).
- **Rest engine**: b2b / 3-in-4 penalties, computed from the ESPN schedule already fetched.
- Star availability weighted harder than MLB (top-heavy sport; usage/minutes-aware weighting where feed allows, count-based fallback).
- Garbage-time cap on EWMA updates (blowout margins lie).
- Live: **Brownian margin diffusion** — lead ± drift, variance ∝ remaining time; canonical live-NBA shape.

### 5.3 NHL
- **Bivariate Poisson goals** (the MLB Skellam machinery ports nearly directly) with an explicit **regulation-tie → OT/SO branch**: Kalshi winners include OT, so P(win) = P(reg win) + P(reg tie)·P(OT/SO win), the latter near-coin with slight strength/home tilt.
- **Goalie starter identity** — the single biggest NHL factor; per-goalie save% EWMA, starter from ESPN probables; unknown starter → wider uncertainty (never a mean shift).
- Live: time-scaled Poisson + **pulled-goalie empty-net inflation** for late totals/spreads.

### 5.4 NCAAF / NCAAMB
- Reuse the NFL/NBA engines with college parameterization: wider sigmas, larger home edge, stronger cold-start priors over huge team universes (360+ NCAAMB teams; ESPN college feeds already wired, including the per-day date-range workaround shipped earlier).
- Neutral-site flag (tournaments/bowls) from ESPN payload.
- Talent-gap regression for mismatch games.

### 5.5 Crypto
The approved 2026-07-12 crypto design becomes the crypto specialist verbatim:
- `autonomy/crypto_implied_book.py` — **Deribit DVOL single-sigma risk-neutral book**: σ_implied_horizon = (dvol/100)·√(hours/(24·365)); book_prob = Φ(ln(spot/strike)/σ_implied_horizon). Reuses `parse_crypto_ticker`, `_hours_to_close`, `_normal_cdf`, floor_strike handling so model and book compare on identical contract terms. Source = already-fetched `CryptoDataHub` state (dvol nulled when >6h stale → book abstains → `model_only`, byte-identical to today). Realized (model) vs implied (book) σ is a genuinely independent-estimator pair.
- **Vol-blend robustness**: Coinbase-primary realized σ with Kraken-closes failover; byte-identical when Coinbase healthy.
- **Event-window uncertainty**: static auditable FOMC/CPI/unlock calendar widens `crypto_probability_uncertainty` inside windows — never shifts the mean; empty table → no-op.
- Governance-gated upgrade slot noted for a Deribit option-chain smile book (NOT built now — DVOL must prove out on settlements first).

## 6. UFC / F1 removal (Phase 0)

Deregister `UfcIntelligenceSignal` + `FormulaOneIntelligenceSignal` (autonomy/session.py), delete `autonomy/sports/ufc.py`, `autonomy/sports/formula_one.py`, their signal classes in `sports_intelligence.py`, tests, and warm state. Scanner untouched — those markets simply route to no specialist → no forecast → no trade. Clean amputation.

## 7. Council observability

Dashboard **Council panel**: one row per specialist — feed freshness, model age, settled n, contested Brier, CLV, open opportunities, health color. No new fleet processes (in-process council).

## 8. Rollout (season-driven; each phase = own plan → PRs → opus review → green CI → merge)

| Phase | Scope | Why this order |
|---|---|---|
| **0** | Master spec, UFC/F1 removal, `autonomy/specialists/` skeleton, migrate MLB + crypto wiring (zero behavior change) | Foundation everything hangs on |
| **1** | Crypto specialist completion (DVOL book, vol-blend, event windows) + CLV grading layer | Crypto is 24/7 live today |
| **2** | MLB improvements (§4) + coherence engine (§3.1) | MLB mid-season NOW — live validation runway |
| **3** | NFL + NCAAF specialists (§5.1, §5.4) | Seasons start late Aug / early Sept — built + paper-validated before kickoff |
| **4** | NBA + NHL specialists (§5.2, §5.3) | October starts |
| **5** | NCAAMB specialist + trust surface (§3.3) + propose-then-promote tuner (§3.4) | November start; reuses Phase-4 NBA engine |

## 8b. Amendment v1.1 (operator directive, 2026-07-12 later same day)

### 8b.1 Confirmed trading surface — all leagues, full ladders
NFL/NCAAF/NBA/NCAAMB/NHL each trade **winners + the full spread ladder + the
full total ladder**. Verified live: "alt" lines are NOT separate series --
they are multiple strikes inside the existing `KX*SPREAD`/`KX*TOTAL` events
(MLB spreads carry 1.5/2.5/3.5 per side; MLB totals carry an 11-strike
2.5-9.5 ladder). Each specialist's joint score distribution prices the
entire ladder coherently by construction; the parsers already read
per-strike `floor_strike`. The coherence engine (section 3.1) extends to
**ladder coherence**: within one game, P(cover 1.5) >= P(cover 2.5) >=
P(cover 3.5) with model-calibrated gaps -- Kalshi's crowd sets each rung
independently, so rung-level incoherence is a structural edge tier.

### 8b.2 Player-matchup + rookie-impact layer (each league)
- Player-state EWMAs from keyless ESPN rosters/depth charts/boxscores:
  QB identity (NFL/NCAAF), usage/minutes stars (NBA/NCAAMB), starting
  goalie (NHL). Position-weighted availability deltas (QB >> RB; star
  minutes; goalie identity).
- **Rookie impacts:** rookie starters flagged from roster experience
  fields. Thin priors make rookie starts the market's misprice zone: widen
  uncertainty on rookie-QB/rookie-goalie/rookie-heavy lineups early, log
  `rookie_start` features, and let the strategy miner grade which rookie
  states carried edge (mined, not assumed).
- **Mismatch finder:** per-league unit-level EWMAs and their deltas --
  NFL pass-offense vs opponent pass-defense, NBA pace/style/rest deltas,
  NHL goalie-quality and special-teams gaps (PP% vs PK%), NCAA
  talent/experience gaps. Bounded challenger drift under the shared
  0.45-sigma cap; every mismatch score logged as features.

### 8b.3 Situational-awareness engine (each league; in-game and between games)
States: trades/roster deltas (transactions feed), rest and
back-to-backs (computable from schedule), coaching changes, gameplan
narratives, playoff seeding/clinch/elimination (standings), bye weeks,
suspensions (status feeds). Doctrine: **hard, verifiable states** (rest,
b2b, bye, clinched/eliminated, suspension, confirmed trade) may apply
bounded per-league mean adjustments; **narrative-soft states** (gameplan
talk, coach-bounce lore) widen uncertainty only and never shift the mean.
All states logged as features so the miner grades which situations pay --
propose-then-promote, like everything else.

### 8b.4 Crypto equities / ETF / treasury-company lane (Phase 1d)
`CryptoEquitiesSignal` challenger via the existing keyless Yahoo chart
pipeline (all symbols verified live 2026-07-12): spot-ETF flow proxies
(IBIT, FBTC, ETHA -- price momentum + volume-surge amplifier, hard-capped),
crypto-beta equities (COIN, MARA, RIOT), treasury companies (MSTR).
Asset-conditioned factor weights (the ETH ETF barely opines on a BTC
strike). Bounded risk-appetite drift like the macro signal
(<= 0.35 sigma); divergence between the equity complex and the spot tape's
own momentum WIDENS uncertainty instead of picking a winner.

Phase mapping: 8b.1 ladder coherence lands with Phase 2's coherence engine;
8b.2/8b.3 land inside each league's phase (MLB gets rest/travel + situational
states in Phase 2); 8b.4 is Phase 1d.

## 9. Testing & governance doctrine (applies to every phase)

- Every new estimator: hand-computed fixture tests (known inputs → asserted probability), abstention tests (missing feed → None), byte-identical fail-closed tests (feature off/absent → unchanged output).
- Every specialist: routing disjointness test; settlement-invariant test (live scores never leak into learning before `status == "post"`).
- Challenger-only until settlement-backed contested-Brier promotion per market type; CLV is corroborating evidence, never the gate.
- Suite green before any merge; standing auto-merge authorization applies; live-trading authority changes remain out of scope for all phases.
