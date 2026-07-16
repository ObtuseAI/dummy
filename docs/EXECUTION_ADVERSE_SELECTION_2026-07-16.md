# Execution adverse-selection diagnosis — 2026-07-16

Wave-1 workstream A1+A3. This report makes maker adverse selection a
first-class measured quantity and records the diagnostic evidence for the
Phase-A execution-policy tournament. All numbers below were produced by the
new instrumentation (`autonomy/adverse_selection.py`,
`autonomy/loss_engine.py --fills`) run **read-only** against the live runtime
ledger (`D:\DummyRuntime\autonomy\ledger.db`, 108,190 settlements, snapshot
2026-07-16). Nothing in this workstream changes allocator or executor
behavior; policy changes belong to the tournament.

Artifacts introduced (produced wherever the backtest summary is produced, by
`scripts/run_dummy_backtest.py` and `scripts/run_dummy_loss_engine.py --fills`):

- `runtime/autonomy/adverse_selection.json` — the full adverse-selection
  report (also embedded in the backtest report as
  `execution_adverse_selection`, headline in the `--summary` view).
- `runtime/autonomy/loss_attribution_fills.json` — loss deconstruction
  restricted to witnessed / would-have-filled markets.

Every interval below is cluster-level (per-event-cluster means, bootstrap over
clusters) — never a per-emission CI.

## Population

One row per actionable decision: non-abstain, submitted (SHADOW/ACCEPTED
outcome exists), settled, with a point-in-time market prior. This is exactly
the set a taker policy would have executed immediately; the maker policy fills
only the crossed subset.

| | n | Event clusters |
|---|---:|---:|
| Actionable settled decisions | 155 | 76 |
| Maker-filled (witnessed cross) | 28 | 23 |
| — of which settled with P&L | 27 | 22 |
| Unfilled (TTL-expired) | 127 | 64 |

Prior reviews cited 22 witnessed fills, −380¢, 0% win (2026-07-14) and
fill-conditioned ECE 0.413 (stale 2026-07-10 summary, n=8). The ledger has
since accumulated to the 28/27 above; the adverse-selection signature is
unchanged in direction.

## 1. Fill-conditioned skill, maker vs taker vs full surface

| Slice | n | Forecast Brier | Market Brier | Brier skill vs market | ECE | Cluster-robust Brier edge CI95 |
|---|---:|---:|---:|---:|---:|---|
| Full actionable surface | 155 | 0.2365 | 0.2435 | **+0.0286** | 0.1345 | — |
| Maker-filled subset | 28 | 0.2654 | 0.2313 | **−0.1474** | 0.2144 | −0.0331 [−0.0820, +0.0169] (23 cl.) |
| Unfilled subset | 127 | 0.2302 | 0.2462 | **+0.0651** | 0.1299 | +0.0199 [−0.0098, +0.0518] (64 cl.) |

Execution P&L, net of fees:

| Policy | n | Net P&L | Win rate | Cluster-robust mean P&L CI95 |
|---|---:|---:|---:|---|
| Maker, realized (ground truth) | 27 | **−431¢** | 0.259 | −17.95¢ [−41.08, +5.24] (22 cl.) |
| Taker counterfactual, same filled subset (per-contract, mid + taker fee) | 28 | −340¢ | 0.286 | — |
| Taker counterfactual, full actionable surface (per-contract) | 155 | **−129¢** | 0.439 | +3.30¢ [−5.38, +12.92] (76 cl.) |

Reading: the model carries genuine skill on the full actionable surface
(+2.9% Brier skill) and especially on the trades it never gets (+6.5%), but
the maker fill mechanism selects the subset where the model is **worse than
the market** (−14.7% skill, ECE 0.214 vs 0.130 unfilled). The taker
counterfactual is conservative (crosses to the mid, pays taker fee) and still
dominates the maker book because it also captures the winning trades the
maker never fills.

## 2. The direct adverse-selection number (fill vs no-fill outcome delta)

- Filled forecast Brier 0.2654 vs unfilled 0.2302 → **gap +0.0352**: the
  model is systematically less accurate on the emissions that fill.
- Filled cluster-robust edge vs market: **−0.0331** [−0.0820, +0.0169];
  unfilled: **+0.0199** [−0.0098, +0.0518]. The filled interval sits almost
  entirely below the unfilled interval — the fill mechanism is selecting the
  model's errors.

## 3. Per-fill slippage: the maker "bargain" is informational

Slippage = fair value for the traded side minus fill price (positive =
"filled below fair").

| Reference price | Mean | Median | p10 / p90 | Cluster-robust CI95 |
|---|---:|---:|---:|---|
| Model fair value (signal_price − fill_price) | **+13.27¢** | 11.37¢ | 7.35 / 21.75 | +13.99 [+11.87, +16.21] |
| Market prior (market_price − fill_price) | **+1.54¢** | 0.50¢ | 0.00 / 4.60 | +1.47 [+0.80, +2.32] |

The model believes every fill is a ~13¢ bargain; the contemporaneous market
prices the same fill within ~1.5¢ of fair. Mean model slippage on winning
fills (13.02¢) is indistinguishable from losing fills (13.06¢) — claimed
model edge at fill time has **zero** discriminating power over outcome. The
13¢ divergence is adverse information, not value.

## 4. Time-to-fill vs the market's move through us

Median time-to-witnessed-fill 261s, p90 1241s. Mean observed cross depth
(how far the book printed through the resting quote at the fill witness):
5.1¢, median 1¢.

| Latency bucket | Fills (settled) | Net P&L | Win rate | Cluster-robust mean P&L CI95 |
|---|---:|---:|---:|---|
| ≤ 60s | 9 | **−300¢** | 0.111 | −37.9¢ [−93.6, +6.2] (7 cl.) |
| 60–300s | 5 | −29¢ | 0.400 | −18.0¢ [−49.3, +24.8] (4 cl.) |
| > 300s | 13 | −102¢ | 0.308 | −10.3¢ [−41.1, +21.7] (12 cl.) |

The worst fills are the **fast** ones: a quote crossed within a minute of
submission was effectively stale/marketable at submit — the book was already
moving through the price when the quote was placed. 9 fills, 1 win, −300¢ of
the total −431¢.

## 5. Where the fills lose (fill-batch loss engine)

`run_dummy_loss_engine.py --fills` over the 32 markets that ever produced a
witnessed fill (2,358 settled emissions, 23 event clusters):

- **Pooled cluster edge: −0.0524 [−0.1111, +0.0062]** — the filled markets as
  a whole trail the market, borderline at the 95% level on 23 clusters.
- Per-scope, every scope is honestly `insufficient_data` (below the
  10-cluster floor). The worst point estimates, thin as they are:

| Scope | Cluster edge | Clusters |
|---|---:|---:|
| `crypto\|sol\|ladder\|unknown` | −0.399 | 1 |
| `weather\|kxhighny\|na\|pre` | −0.264 | 2 |
| `weather\|kxhighmia\|na\|pre` | −0.242 | 1 |
| `crypto\|sol\|ladder\|hourly` | −0.185 | 1 |
| `weather\|kxhightsea\|na\|pre` | −0.169 | 1 |
| `crypto\|btc\|ladder\|hourly` | −0.079 | 5 |
| `crypto\|eth\|ladder\|hourly` | −0.050 | 3 |

Settled-fill P&L by vertical points the same way: crypto −462¢ (12 fills),
weather −95¢ (8), sports +43¢ (6), commodities +83¢ (1). **Crypto ladder
fills are the bleed**; the biggest identifiable losing regime is
fast-crossed crypto hourly/sub-hourly ladders.

## 6. Guard counterfactuals (observed-fill censoring; no invented fills)

Filters applied to the 27 settled fills. These drop observed fills only —
they cannot add the fills a different policy would have attracted.

| Guard | Kept | Net P&L | Win rate |
|---|---:|---:|---:|
| None (incumbent maker) | 27 | −431¢ | 0.259 |
| A: drop fills witnessed ≤60s | 18 | −131¢ | 0.333 |
| B: rest only when \|model−market\| ≤ 10¢ | 12 | −51¢ | 0.333 |
| A + B | 10 | **−8¢** | 0.400 |

Taker-at-mid with a minimum model-edge threshold over the full actionable
surface (in-sample, descriptive only — honest selection must come from the
existing walk-forward machinery):

| Min \|model−market\| | n | Net P&L | Win rate |
|---|---:|---:|---:|
| 0¢ | 155 | −129¢ | 0.439 |
| 3¢ | 148 | −34¢ | 0.439 |
| 5¢ | 128 | +814¢ | 0.477 |
| 8¢ | 108 | +910¢ | 0.472 |
| 10¢ | 83 | +694¢ | 0.482 |

## 7. Recommendation: Phase-A tournament cohorts

The evidence says the forecast surface has modest positive skill but the
maker execution channel converts it into a losing book by filling only the
model's mistakes. The tournament should therefore test execution policy, not
forecast policy, with the incumbent as control:

1. **C0 — maker-only (control).** Current allocator/executor unchanged.
2. **C1 — taker-only.** Cross immediately at the best ask at decision time,
   taker fee, same MIN_EV=3¢ *net of taker fee and observed half-spread*.
   Rationale: taker over the full surface holds the whole +2.9% Brier-skill
   population instead of the adversely selected −14.7% subset.
3. **C2 — taker-only with walk-forward edge threshold.** Same as C1 but the
   minimum model-edge threshold is chosen per fold by the existing
   `walk_forward_threshold_selection` machinery (in-sample table above
   suggests the 5–8¢ region, but the tournament must not hardcode an
   in-sample pick).
4. **C3 — adverse-guard maker.** Maker quoting with both observed guards:
   (a) fast-cross guard — a fill witnessed ≤60s after submit is treated as
   marketable-at-submit; pre-submit fresh-book recheck (the live `quote_fn`
   guard, extended to shadow) must reject quotes within 1 tick of crossing;
   (b) divergence cap — do not rest a quote when \|model − market\| > 10¢
   (the observed A+B censor retains 10/27 fills at −8¢ vs −431¢).
5. **C4 — hybrid patient-then-take.** Rest maker for 60s; if unfilled and
   the fresh book still clears MIN_EV net of taker fee, cross; else cancel
   (crypto keeps its existing 60s TTL, i.e. C4 ≈ C1 for crypto).
6. **Vertical asymmetry option (if slots are scarce):** run C1/C3 on crypto
   first — crypto ladders are where the maker book bleeds (−462¢ of −431¢
   total; sports and commodities fills are net positive on tiny samples).

Success gate per cohort (consistent with house rules): ≥ 40 event clusters
of witnessed (or would-have-witnessed) fills, cluster-robust mean P&L CI and
fill-conditioned Brier-edge CI compared against C0; promotion of any cohort
remains a separate human decision.

## Caveats

- 27 settled fills / 22 clusters is a small sample; the point estimates are
  directional and the cluster CIs are the honest object. The maker P&L CI
  still straddles zero ([−41.1, +5.2]¢/fill); what is *not* ambiguous is the
  calibration split (filled 0.2654 vs unfilled 0.2302 Brier, slippage CI
  [+11.9, +16.2]¢ vs [+0.8, +2.3]¢).
- Guard counterfactuals censor observed fills; they cannot model the fills a
  changed policy would attract or repel. That is what the tournament is for.
- Taker threshold rows are in-sample and descriptive; only the walk-forward
  selection is admissible evidence.
- Read-only measurement. No execution, capital, or promotion authority; no
  live behavior changed in this workstream.
