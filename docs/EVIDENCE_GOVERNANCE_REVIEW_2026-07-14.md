# Bundle 2 evidence and governance review — 2026-07-14

## Items 4–6 refresh — 2026-07-14 19:52Z

**Completed decision: keep both experiment and promotion gates closed.** This
refresh supersedes the point-in-time counts below where they differ. The ledger
added 694 settled markets since the earlier review (85,367 to 86,061), but it
added no witnessed settled trades and no fill-conditioned calibration rows.
Operational results therefore remain 22 witnessed settled shadow trades across
19 event clusters, net **-380 cents**, with a 0.4062 profit factor and -48.72%
ROI on entry cost.

Fill-conditioned calibration also remains negative: forecast Brier is
0.242447 versus market Brier 0.208959, a mean advantage of **-0.033488** with
95% interval [-0.084257, 0.017280]. Forecast log loss is 0.726554 versus market
log loss 0.614914. The crypto witnessed-fill subset remains 11 decisions, net
**-282 cents**, with ensemble Brier 0.253315 versus market Brier 0.185064.

The refreshed mechanical readiness report lists only two promotion candidates:

| Scope | Clusters | Mean edge | 95% interval | Decision |
|---|---:|---:|---:|---|
| `crypto_equities_flow|15m_direction|15m` | 485 | 0.011316 | [0.003178, 0.019454] | Mechanically eligible; experiment deferred |
| `crypto_blend_sigma|15m_direction|15m` | 440 | 0.009803 | [0.001465, 0.018141] | Mechanically eligible; experiment deferred |

Item 5's bounded crypto shadow experiment is **not launched**. The preferred
first candidate, `crypto_empirical_regime`, is no longer mechanically eligible
in the refreshed report, while the two eligible scopes do not overcome the
negative witnessed-fill evidence. Launching a new treatment now would add
another correlated comparison before the current execution problem has
accumulated enough new fills to distinguish signal quality from fill selection.

Item 6's promotion review is **NO-GO**. The explicit prerequisites—positive
fill-conditioned calibration and positive settled P&L—are both unmet. No
`promotions.json` exists, no source weight was written, no automatic demotion
was produced, and execution/capital authority remains closed. Re-open items 5
and 6 only after materially more witnessed fills settle and both operational
gates turn positive.

Refreshed artifacts:

- `runtime/autonomy/strategy_mining_report.json` (686,967 settled rows; 12 candidates)
- `runtime/autonomy/clv_report.json` (96 graded entries; 37 event clusters)
- `runtime/autonomy/loss_attribution.json` (24 scopes; 13 bleeding scopes)
- `runtime/autonomy/readiness_report.json` (54 scopes; two mechanical candidates)
- `artifacts/dummy/backtests/AUTONOMY_BACKTEST_20260714T195201110138.json`

## Decision

**DEFER every promotion and every sports retune.** The four crypto scopes pass
the mechanical contested-Brier readiness rule, but Dummy's operational evidence
does not yet justify adding them to the execution ensemble: 22 witnessed,
settled shadow trades are net **-380 cents**, fill-conditioned Brier is worse
than the market, and the crypto witnessed-fill subset is **-282 cents**. No
`promotions.json` was created or changed.

This is a point-in-time review, not a capital authorization. It used the
read-only ledger and the following refreshed artifacts:

- `runtime/autonomy/readiness_report.json`
- `runtime/autonomy/loss_attribution.json`
- `runtime/autonomy/clv_report.json`
- `runtime/autonomy/strategy_mining_report.json`
- `artifacts/dummy/backtests/AUTONOMY_BACKTEST_20260714T181917801855.json`

## Forward accumulation

The live accumulation path is armed and healthy. `DummyMispricingMonitor`,
`DummySportsSimulation`, `DummyStrategyMiner`, and `DummyReadinessReport` all
reported successful last completions. MLB is the only active team specialist;
NBA, NFL, NCAAF, NHL, and NCAAMB are correctly season-dormant.

At this snapshot, the newly registered `mlb_pa_live_*`, `nfl_live_*`,
`ncaaf_live_*`, `ncaamb_live_*`, `nba_live_*`, and `nhl_live_*` sources have
zero emissions. That is an honest empty result: no qualifying live MLB
StatsAPI hydration window occurred, and the other leagues are out of season.
No retro rows, synthetic games, or lower-quality substitutes were inserted to
make the counters move. The running monitor will record the first qualifying
forward observations automatically.

### Forward activation verification — 2026-07-14 19:33Z

The two accumulation tasks were explicitly triggered after the live-model
bundle was published. Both completed with Windows Task Scheduler result `0`:

- `DummyMispricingMonitor` scanned 1,466 markets, produced one shortlist row
  and zero actionable opportunities, and remains scheduled every two minutes.
- `DummySportsSimulation` cycle `sports-20260714T193259` saw 87 sports markets,
  wrote 61 point-in-time observations, reported no errors, and remains
  scheduled every ten minutes.

The sports cycle's authority record remained fully closed: public GET only,
challenger only, no credentials, no broker contact, no execution authority,
and no capital authority. The newly registered live source count remained zero
because the slate contained no qualifying in-progress state. This verifies the
forward collection path without mislabeling ordinary pregame observations as
live evidence.

## Sports diagnosis

No sports scope has the required 300 independent event clusters. The current
evidence says to accumulate rather than tune:

| Scope | Clusters | Mean Brier edge | 95% interval | Decision |
|---|---:|---:|---:|---|
| `sports_elo|na|pre` | 61 | -0.008858 | [-0.026520, 0.008805] | Degrading; do not tune a mixed aggregate |
| `sportsbook_consensus|na|pre` | 56 | -0.001570 | [-0.005568, 0.002429] | Inconclusive; continue accrual |
| `mlb_structural_winner|winner|pre` | 45 | 0.018155 | [-0.005081, 0.041392] | Promising, underpowered |
| `mlb_total_runs|total_runs|pre` | 44 | -0.011277 | [-0.027959, 0.005405] | Negative mean, inconclusive; no retune |
| `mlb_live_winner|winner|live` | 15 | 0.021362 | [-0.003034, 0.045758] | Promising, very thin |
| `mlb_live_total|total_runs|live` | 15 | -0.004246 | [-0.026648, 0.018156] | Inconclusive; no retune |
| `mlb_live_spread|spread|live` | 15 | 0.004328 | [-0.007961, 0.016618] | Inconclusive; continue accrual |

The broad `sports_elo` and `sportsbook_consensus` scopes currently carry
`market_type=na` and combine league contexts. Their negative aggregate means
are useful warnings, not valid league-specific tuning targets. A parameter
change from those pooled rows would be premature and could erase a healthy
league to compensate for an unhealthy one.

## Crypto candidate review

All counts below are independent event clusters from the refreshed readiness
report. “Live-settled markets” is restricted to the reviewed 15-minute scope.

| Scope | Clusters | Mean edge | 95% interval | Live-settled markets | Review |
|---|---:|---:|---:|---:|---|
| `crypto_blend_sigma|15m_direction|15m` | 422 | 0.011566 | [0.003118, 0.020013] | 445 | Defer; alternate transform of the incumbent crypto distribution |
| `crypto_empirical_regime|15m_direction|15m` | 1,066 | 0.007857 | [0.002002, 0.013713] | 1,093 | Defer; strongest sample, but operational fill evidence is still negative |
| `crypto_equities_flow|15m_direction|15m` | 467 | 0.013059 | [0.004812, 0.021306] | 490 | Defer; nearly collinear with macro drift |
| `crypto_macro_regime|15m_direction|15m` | 578 | 0.007828 | [0.000497, 0.015158] | 604 | Defer; lower confidence bound is only marginally positive |

The specialist-level 15-minute CLV sample is positive, but it contains only
six event clusters and is not attributable to any one challenger. It supports
continued study, not promotion.

Point-in-time candidate shifts were compared against the contemporaneous
`crypto_spot_vol` baseline. `crypto_equities_flow` and
`crypto_macro_regime` had **0.990905 Pearson correlation** across 657 aligned
settled observations. `crypto_blend_sigma` and `crypto_empirical_regime` are
alternative transforms of the same crypto tape used by the incumbent. The
forecaster therefore pools blend/empirical with the Coinbase distribution
family and macro/equities with one cross-asset-drift family. A future human
promotion can redistribute weight inside those families but cannot create
additional precision merely by enabling correlated sources.

## Next evidence gate

Keep the current shadow-only posture. Re-run this review after forward sports
sources emit and settle, or after materially more witnessed fills exist. If a
later bounded shadow experiment is explicitly approved, evaluate one candidate
family member at a time—`crypto_empirical_regime` before another distribution
transform, and `crypto_equities_flow` before `crypto_macro_regime`. Promotion
to capital still requires a separate human-authored decision citing the then-
current readiness, fill-conditioned calibration, and settled P&L evidence.
