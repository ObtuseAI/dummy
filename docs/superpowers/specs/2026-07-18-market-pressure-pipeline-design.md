# Market-Pressure Pipeline — design

**Date:** 2026-07-18
**Operator directive:** "create or improve a state-of-the-art pipeline for public betting money/tickets — line-movement patterns, sheep/sharp — avoiding traps and finding underdogs. As a sports gambler that's just as important to my success as actual matchups."
**Decisions locked (operator):** (1) source betting splits by **scraping** public aggregators — relax the replicate-not-scrape boundary for betting-market data; (2) integrate **both** as a fusion challenger signal **and** an operator-facing sharp-read report.

## Thesis

The line is the sharpest public forecast of a game, and *how it got there* — who moved it, when, against which crowd — carries information the closing number alone hides. A square (public / "sheep") crowd leans predictably: favorites, home teams, overs, popular franchises, primetime, big spreads. When the market moves **against** that predictable lean, professional ("sharp") money is the cause. Capturing that pressure lets us do the two things the operator named: **avoid traps** (heavy public on a side the market won't confirm) and **find underdogs** (dogs the sharp/steam/RLM points at while the public is on the favorite).

## What already exists (the "improve" base)

- `autonomy/signals/sportsbook.py` — `SportsbookConsensusSignal`: de-vigs one book's two-way moneyline, computes open→now "steam" for the subject. Single book, single snapshot.
- `autonomy/signals/licensed_consensus.py` — `LicensedConsensusSignal`: multi-book de-vig (~8 US books via the Odds API), h2h/totals/spreads.
- `autonomy/odds_api_budget.py` (Wave-12) — the **odds payload archive**: every paid Odds API fetch is appended to a monthly gzip JSONL shard `{ts, key, remaining, payload}` at `DUMMY_ODDS_ARCHIVE_DIR` (live box: `D:\dummy-data\odds_archive`). A multi-book line-movement time series that nothing currently reads back.
- `autonomy/clv.py` / `autonomy/sports_clv.py` — closing-line-value tracking.
- `autonomy/mispricing.py` / `mispricing_monitor.py` — Kalshi-vs-fair mispricing surface.

## The gap

Nothing turns the archive into movement intelligence. There is no cross-book steam, no book-dispersion / soft-line detection, no model of the public lean, no reverse-line-movement inference, no betting-splits ingestion, and no trap / underdog synthesis.

## Architecture — units, each independently testable

1. **Movement featurizer** — `autonomy/market_pressure/line_movement.py`
   - Input: the Wave-12 odds archive (gzip JSONL) + optionally the live cached payload.
   - Output: per (game, book, market, side) time series → `opener`, `current`, `path`, `velocity` (prob/hour over the last window), `total_travel`, `n_snapshots`, `first_seen`, `last_seen`. All in de-vig **probability space** (reuse `sportsbook.devig_two_way` / a totals/spreads de-vig).
   - Pure function core `movement_series(records, now)`; no I/O in the core. A thin archive reader (`read_archive_window`) feeds it.
   - Depends on: archive format only. Knows nothing about signals or fusion.

2. **Cross-book steam detector** — `autonomy/market_pressure/steam.py`
   - Input: the per-book series for one game/market/side.
   - Output: `SteamRead` — `is_steam` (≥K of N books moved the same direction ≥θ within a short window), `magnitude`, `direction`, `originator` (book that moved first), `followers`, `synchrony` (how tight in time). One-sided; fail-closed when <2 books.
   - Depends on: featurizer output only.

3. **Dispersion / soft-line** — `autonomy/market_pressure/dispersion.py`
   - Input: current per-book de-vig probabilities for a game/market/side.
   - Output: `DispersionRead` — trimmed consensus, spread, the outlier book(s) and their signed offset (the soft/beatable number), `is_stale_outlier`. Fail-closed when <3 books.

4. **Public-lean model** — `autonomy/market_pressure/public_lean.py`
   - Input: game structural features (favorite/dog, home/away, spread magnitude, total, franchise-popularity table, primetime flag, day/national-TV).
   - Output: `public_lean` = P(the square crowd is on this side), 0..1, plus the driving factors. Starts as a transparent heuristic prior (documented weights); a later refit learns weights from settled RLM behavior. No ticket data required.
   - Depends on: a small static `POPULAR_FRANCHISES` table + the market's structural fields.

5. **Splits provider (scraped)** — `autonomy/market_pressure/splits/` (Wave-31)
   - `SplitsProvider` protocol → per-game `SplitsRead` (`ticket_pct`, `money_pct` per side, `book_or_aggregate`, `as_of`, `source`).
   - Per-source scrapers behind the protocol (start with the least-fragile public JSON endpoint; add HTML sources as adapters). **Responsible-scraping contract** (see governance below).
   - A governor mirroring `OddsApiBudget`: cache-first (splits move slowly — refresh ≤ every 10–15 min per source), realistic headers, exponential backoff on 429/5xx, per-source archive shard `splits_<month>.jsonl.gz`, **fail-open** on fetch (never crash a cycle), **fail-closed** on the read (no data → no splits opinion). Inert unless `DUMMY_SPLITS_ENABLED=1`.

6. **Synthesis** — `autonomy/market_pressure/pressure.py`
   - Combine featurizer + steam + dispersion + public-lean (+ splits when armed) into a single `MarketPressureRead` per game/side: `sharp_side`, `public_side`, `steam`, `reverse_line_movement` (line drift toward the public-unpopular side; true RLM = line vs ticket-majority when splits armed), `trap_flag` (heavy public + line not confirming / moving against), `dog_value_flag` (sharp/steam/RLM on the dog while public on the favorite), and a bounded `pressure_prob_adjustment`.

7. **Challenger signal** — `autonomy/signals/market_pressure.py`
   - `MarketPressureSignal` (name `market_pressure`): applies the synthesis's capped adjustment to the market's de-vig baseline; `challenger_only=True`, fail-closed, full audit features, graded on settlement **and** CLV like every other sports challenger. Session-registered after `licensed_consensus`.

8. **Sharp-read report** — board + dashboard
   - `assemble_sharp_read()` writes `runtime/autonomy/sharp_read.json` (per-game: sharp side, public side, steam originator, RLM, trap flag, dog-value, dispersion/soft book). Surfaced as a dashboard card (fast-snapshot, ledger-free, like the vNext/USE cards) and a bet-board annotation.

## Data flow

archive (+ live cache) → featurizer → {steam, dispersion} ┐
game structure → public-lean ──────────────────────────────┤→ synthesis → { challenger signal → fusion (graded) ; sharp_read.json → dashboard/board }
scraped splits (when armed) → splits provider ─────────────┘

## Error handling & discipline

- Every external read **fail-open** (a scrape/archive error never breaks a cycle); every **opinion** fail-closed (missing/degenerate inputs → no signal, no adjustment).
- All new probability influence is **challenger-only** and **capped**; promotion to trusted weight stays behind Dummy's predictive and forward witnessed-fill evidence gates (human-only to capital). Preregister the `market_pressure` challenger (hypothesis, mechanism, falsification incl. an abstention-rate floor) via the Wave-7 machinery before it can earn trust.
- The pipeline never places or sizes a bet; it informs the forecast and shows the operator the sharp/public picture.

## Governance change — scraping (operator-directed 2026-07-18)

dummy's prior doctrine was keyless-only / replicate-not-scrape (see `docs/PLAYER_PROPS.md`, `autonomy/odds_providers.py`, the phenon-harness spec). Per operator directive this is **relaxed for public betting-market data** (splits, consensus %, line-movement aggregates) under a **responsible-scraping contract**:

- Cache-first and low-frequency (data updates slowly; no tight-loop polling).
- Realistic headers, rate limiting, exponential backoff, honor 429/Retry-After.
- Fail-open fetch, fail-closed opinion; every fetch archived to build proprietary history.
- Multiple sources cross-checked; a source that changes shape degrades to no-opinion, not garbage.
- ToS reality acknowledged in-code and in docs: these endpoints are public but their ToS generally forbids automated access; this is the operator's own system and accepted risk. Scope is betting-market data plus, on the **same** responsible framework, other clearly-useful public betting data as it comes up. Unrelated ToS-restricted domains (recruiting composites, proprietary grades) keep their existing posture unless separately directed.

## Implementation sequence (waves)

- **Wave-29 (foundation, no scraping):** movement featurizer + cross-book steam + dispersion, over the existing archive. Immediate value, zero new data/governance. This spec commits here.
- **Wave-30:** public-lean model + RLM inference + synthesis + `market_pressure` challenger into fusion (preregistered).
- **Wave-31:** responsible splits scrapers + governed provider + splits archive + money/ticket divergence + trap detection wired into synthesis.
- **Wave-32:** sharp-read report (dashboard card + bet-board annotation) + operator "traps & dogs" view.

## Success criteria

- Featurizer reconstructs a game's multi-book movement from the archive with correct opener/current/velocity in probability space.
- Steam fires only on genuine multi-book synchronized moves (not one book twitching); dispersion names the soft book.
- The `market_pressure` challenger accrues a graded record on settlements + CLV and is subject to the same promotion doors as every other challenger — no automatic capital authority.
- The sharp-read surface shows, per game, a defensible sharp side / public side / trap / dog-value call an experienced bettor would recognize.
