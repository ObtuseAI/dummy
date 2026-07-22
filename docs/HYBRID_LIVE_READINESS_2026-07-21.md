# SUPERSEDED HISTORICAL SNAPSHOT — Gemini 3.5 Flash / GPT-5.6 Terra

> **SUPERSEDED — DO NOT USE FOR CURRENT READINESS OR AUTHORITY.** This file is
> retained only as the 2026-07-21 record of a retired two-model configuration.
> The current exact panel is Gemini 3.6 Flash, GPT-5.6 Luna, Claude Sonnet 5,
> and GLM-5.2, documented in
> `docs/OPENROUTER_FOUR_MODEL_PANEL_2026-07-22.md`. None of the live-model
> smokes, test counts, ledger rows, prices, or performance statements below
> validates that four-model panel. All Gemini 3.5 Flash / GPT-5.6 Terra model
> evidence has zero authority under the new
> `openrouter_gemini36flash_gpt56luna_claudesonnet5_glm52_v1` lineage.

Historical date: 2026-07-21  
Repository: `C:\src\engine\dummy`  
Historical verdict (not current): **ENGINEERING READY FOR CONTINUED SHADOW PROOF; LIVE MONEY REMAINS BLOCKED BY PERFORMANCE EVIDENCE**

## Historical changes recorded on 2026-07-21

- OpenRouter routing now directs forecast/thesis/draft work to
  `google/gemini-3.5-flash` and critique/risk/calibration work to
  `openai/gpt-5.6-terra`.
- Production debate is an exact two-model hybrid. Legacy configured models and
  CLI voices cannot silently enter it.
- Both directed voices must answer with valid JSON. A one-model result is
  discarded rather than mislabeled as a hybrid.
- Gemini is prompted as an independent base-rate forecaster; Terra is prompted
  as a skeptical resolution/risk reviewer. Neither may invent facts outside
  the supplied rules, book, quantitative estimate, and tape.
- The aggregate is an equal-weight bounded mean. Self-reported confidence only
  widens uncertainty; it never steers the probability. Each raw model move is
  capped at 15 probability points from the quantitative base.
- Raw Gemini and Terra opinions are persisted as observational-only settlement
  evidence. Only one bounded `llm_debate` aggregate enters fusion.
- C1 taker entries are now selected at the executable ask with the taker fee,
  not at a maker quote that the executor later replaces. Negative gross edge
  and fee-adjusted EV fail before sizing.
- Filled positions now receive fee-aware, executable-bid exit advice. The
  advice is persisted for later settlement replay but is explicitly
  `shadow_advisory_only`; it has no broker sell authority.

## Historical validation evidence for the retired panel only

- Focused hybrid/routing/entry/exit tests: **93 passed**.
- Expanded model/routing/execution regression slice: **385 passed**.
- Full repository suite: **6,647 passed, 1 skipped, 0 failed** in 466.81s.
- Dashboard production build: **PASS**, 360 modules transformed.
- Direct paid OpenRouter smoke:
  - Gemini 3.5 Flash: strict JSON PASS, fair-coin probability 0.50.
  - GPT-5.6 Terra: strict JSON PASS, fair-coin probability 0.50.
- Full two-round live-model hybrid smoke: **PASS**; both exact providers,
  probability 0.50, uncertainty 0.0805, separate observation sources plus one
  aggregate source.
- Deployed scheduled shadow cycle: **CYCLE_OK**, 3,594 markets scanned, 24,729
  signals accepted, 0 rejected, 0 orders, total 517.83s. Hybrid phase was
  47.76s; the main latency was signal generation at 329.17s.
- The production ledger contains separate current-cycle rows for
  `llm_panel_gemini_3_5_flash`, `llm_panel_gpt_5_6_terra`, and `llm_debate`.
- Watchdog: healthy, no stale tasks, no kill file, ledger below its configured
  maximum.
- Signed broker balance read: **PASS**; configured canary minimum funding met.
- `configs/live_submit.json`: `enabled=false` (unchanged).

The OpenRouter model catalog was checked before configuration. At that check,
Gemini 3.5 Flash and GPT-5.6 Terra were both listed with structured-output and
reasoning support. Prices were pinned for cost telemetry at the then-current
catalog rates; they are telemetry inputs, not trading assumptions, and should
be refreshed if OpenRouter changes them:
<https://openrouter.ai/api/v1/models>

## Hard blockers recorded on 2026-07-21

Canary readiness is **false**:

1. Decision-ensemble Brier advantage does not have a positive event-cluster
   95% lower bound.
2. Walk-forward mean PnL does not have a positive 95% lower bound.
3. Verified shadow PnL is -669 cents.
4. Fill-conditioned Brier skill versus market is -0.1491.
5. Crypto fill-conditioned Brier skill is -0.2721.
6. Sports fill-conditioned Brier skill is -0.0821.

Scale readiness is **false**:

- Verified net PnL is not positive.
- Fill-conditioned skill is not positive.
- Crypto has 13/20 required fill-conditioned settlements.
- Sports has 16/20 required fill-conditioned settlements.
- Negative forecast drift is statistically detected (local Brier-excess change
  0.029309).

The market-beating sources reported by the gate at the time of this snapshot were
`crypto_patience_confirm` and `sports_scoring`. They do not erase the negative
execution-conditioned book.

## Historical operational conclusion

Dummy is no longer waiting on model configuration, credentials, build health,
or a missing decision path. It is deployed in shadow with the new hybrid,
executable C1 entry screening, and durable exit observations. It is **not yet
safe to risk live money** because the observed book has lost money and has not
beaten the market with statistical confidence.

No live session was created, no evidence gate was bypassed, no live order was
submitted/cancelled/amended, and no risk cap or firewall was weakened. The
honest route to live is for the existing scheduler to accumulate forward
settlements under these corrected entry/hybrid rules until the unchanged
canary gate turns positive. Model eloquence is not proof of predictive edge.
