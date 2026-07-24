# Dummy exact four-model OpenRouter panel

Date: 2026-07-22  
Repository: `C:\src\engine\dummy`  
Status: **EXACT LIVE CONNECTIVITY PROVEN; CONTINUOUS MODEL CALLS AND LIVE ORDERS GATED**

This is the current model-panel contract. It replaces the retired Gemini 3.5
Flash / GPT-5.6 Terra configuration. The four models increase diversity of
research review; they do not establish predictive edge, grant probability
authority, or make Dummy live-ready by themselves.

## Exact roster and seven-call routing

| Call | Required provider/model | Independent bounded responsibility |
|---:|---|---|
| 1 | `gemini_3_6_flash` / `google/gemini-3.6-flash` | Extract material facts from supplied data and produce the primary probability pass |
| 2 | `gpt_5_6_luna` / `openai/gpt-5.6-luna` | Produce a low-latency independent structured forecast plus a research-only trade draft |
| 3 | `glm_5_2` / `z-ai/glm-5.2` | Seek a decisive no-trade reason and missing-evidence blockers |
| 4 | `claude_sonnet_5` / `anthropic/claude-sonnet-5` | Perform deep strategy critique and expose structural failure modes |
| 5 | `glm_5_2` / `z-ai/glm-5.2` | Attack risk assumptions and try to falsify the working hypothesis |
| 6 | `claude_sonnet_5` / `anthropic/claude-sonnet-5` | Synthesize the deep market thesis, including bullish and bearish evidence |
| 7 | `glm_5_2` / `z-ai/glm-5.2` | Challenge calibration, overconfidence, and omitted falsifying conditions |

The calls are statically routed and independent; no voice sees another voice's
response. Gemini and Luna cover fast structured first passes, Claude supplies
deep strategy and synthesis, and GLM supplies an independent adversarial
perspective. This is deliberate role diversity, not four copies of one prompt.

## Atomic fail-closed contract

The review is accepted only when all seven expected envelopes are present and
the set of provider/model identities is exactly the four-row roster above.
Order does not matter; membership and multiplicity do. The whole model batch
degrades to the untouched quantitative baseline when any envelope is:

- missing, duplicated, or extra;
- returned by the wrong provider, model, or task route;
- a mock, fallback, timeout, or provider failure; or
- invalid JSON, the wrong schema/type, non-finite or out-of-range, internally
  inconsistent, or otherwise semantically malformed.

Partial model success never becomes a smaller hybrid. A valid response is
still bounded research: it cannot directly change execution gates, risk caps,
order parameters, promotion state, or capital.

## New evidence lineage; prior evidence has zero authority

The current probability-authority lineage is:

`openrouter_gemini36flash_gpt56luna_claudesonnet5_glm52_v1`

Retired Gemini 3.5 Flash / GPT-5.6 Terra evidence and any evidence from an
interim, missing, substituted, duplicated, or expanded roster has zero weight
under this lineage. It cannot be renamed, pooled, or grandfathered into the
four-model record. Raw current-panel outputs begin as observational challenger
evidence only.

For an exact sports or crypto scope to earn any probability weight, a separate
explicit promotion dossier must point to a canonical JSON evidence artifact
inside an approved evidence root and match its SHA-256 digest. The artifact
must prove all of the following:

- all four exact provider/model slugs;
- receipt-bounded, point-in-time forward settlements with zero retro rows;
- evidence no more than seven days old;
- at least 300 unique independent event-cluster IDs for the exact scope; and
- a positive lower bound of the event-cluster 95% confidence interval for
  Brier edge.

The earned probability weight is capped at `0.35`. Missing, stale, malformed,
cross-scope, duplicated, tampered, self-promoting, or explicitly demoted
evidence returns weight `0.0`.

## Operational state

- `configs/model_routing.json` keeps `live_model_calls_enabled=false`.
- `configs/live_submit.json` keeps `enabled=false`.
- The project-root `.env` resolves a non-empty `OPENROUTER_API_KEY` through the
  redacted credential resolver; the value is never serialized or logged.
- A bounded manual smoke at `2026-07-22T08:42:34.441622+00:00` made exactly one
  no-retry request to each required model. All four returned HTTP 200, identified
  themselves with the exact requested model slug, and passed their production
  task-shaped JSON contract. The reported cost of that successful four-call run
  was `$0.002273484`.
- The redacted proof is
  `artifacts/dummy/openrouter_four_model_smoke_v1.json`. It stores no prompt,
  response content, exception detail, or credential value.
- Continuous background inference remains a two-key gate: the literal JSON flag
  and `DUMMY_DEBATE_LIVE=1` must both be true. The current JSON flag is false, so
  the persistent runtime opt-in cannot independently arm paid calls.
- The router is not the only boundary: every real provider adapter requires a
  process-local network capability minted after the strict gate. Direct adapter
  calls without it fail before reading a credential or creating an HTTP client.
- The legacy model resolver is preflight-only by default. Its explicit live
  mode requires both literal `allow_live=True` and a valid capability, validates
  a credential-to-HTTPS-host allowlist before key access, and caps alias probes.
- Archived V8 provider/report generators are preflight-only by default, and the
  pytest suite installs an autouse transport interlock that blocks real traffic
  to every approved paid-model host while still allowing local mock transports.
- If continuous research is later enabled, the scheduled debate is hard-clamped
  by market count, concurrency, logical-call count, conservative per-cycle USD
  preflight, and zero retries for the exact four providers.
- No live order was placed, cancelled, amended, or authorized by this panel
  change.
- Enabling research calls in the future remains separate from satisfying the
  canary/scale gates and from explicit operator authorization for any external
  order action.

The current engineering target is therefore honest shadow evidence under the
new exact lineage. Model quality is a hypothesis; only forward calibration and
execution-conditioned settlement evidence can promote it.

## Enforced daily USD ceiling

Spend used to be observed but never bounded: `model_router/cost_tracker.py`
aggregates provider-reported cost inside one process, and the daemon builds a
fresh router every cycle, so nothing accumulated and nothing could refuse.
`model_router/spend_governor.py` is the enforcement half.

- The cap is `DUMMY_LLM_DAILY_USD_CAP`, in USD per UTC day, default `5.00`. A
  missing or malformed value falls back to that default; `0` refuses every paid
  call.
- The ledger is `runtime/autonomy/llm_spend_budget.json` (override with
  `DUMMY_LLM_SPEND_STATE_PATH`) and is rewritten atomically, so the ceiling
  binds across the process-per-cycle brain instead of resetting with it. The
  counter rolls at UTC midnight.
- `ModelRouter.call` RESERVES a call's worst-case price — the route's configured
  per-million prices applied to the prompt and the full requested `max_tokens` —
  before the provider is contacted, then reconciles it against the provider's
  reported cost. A failed or unreported call keeps its reservation: a request
  that left the process may have been billed either way.
- A refused call never reaches the network. It returns the mock voice with
  `fallback_reason=llm_daily_spend_cap_reached` — or `blocked_by`, when mock
  fallback is off — which every existing consumer already discards, and the cost
  summary counts it under `spend_capped_calls`.
- The governor fails closed on its own state: an unreadable or unwritable ledger
  refuses paid calls rather than silently restarting the count.
- `mock` and the local-CLI voices (`claude_cli`, `codex_cli`, which bill a
  personal subscription rather than tokens) never consume the budget, and with
  `live_model_calls_enabled=false` nothing is ever reserved.
- Scope: the ceiling governs the router. The two manual smokes
  (`model_router/smoke.py`, `model_router/openrouter_panel_smoke.py`) contact
  providers directly under an explicit `allow_live` argument and are bounded by
  their own one-call-per-model, zero-retry contract instead.

## 2026-07-24 (Wave-85): measured verdict — the panel stays dark

The panel was **not re-armed**, on evidence rather than caution.

### It was already dark, and not by a switch

Config read as fully enabled — `DUMMY_DEBATE_LIVE=1`, and all three `llm`
switches (`claude`, `codex`, `openrouter`) `true` in `configs/switches.json`.
The ledger disagreed: **zero** `llm_panel*` / `llm_debate*` signals in the
trailing 24 hours, with the last emission at **2026-07-22T08:24:49Z** — the
same day this document was written. The four v3 voices emitted exactly **one**
signal each on that date and then stopped. So there is no flag to flip; the
panel stopped on its own and the cause is undiagnosed.

### It was measurably worse than the model it would join

`autonomy/llm_value_report.py` had never produced a report — it was one of the
two writers dead on `no such table: signal_history`, and once that was fixed it
timed out against its 120s writer budget on every pass. Wave-85 made it
complete in 14.8s, so this is the first actual grading:

| voice | paired rows | voice Brier | fused Brier | adds value |
|---|---|---|---|---|
| `llm_debate` | 1116 | 0.152025 | **0.104823** | no |
| `llm_panel_gpt_5_6_terra` | 616 | 0.164660 | **0.113344** | no |
| `llm_panel_gemini_3_5_flash` | 616 | 0.163383 | **0.113344** | no |
| `llm_debate_v2_98a71ebaf349` | 358 | 0.186443 | **0.145632** | no |
| `llm_panel_v2_gpt_5_6_terra` | 358 | 0.190050 | **0.145632** | no |
| `llm_panel_v2_gemini_3_5_flash` | 358 | 0.185648 | **0.145632** | no |

`adds_value_over_fused` is **false** for all six graded voices. Lower Brier is
better, so every voice is worse than the ensemble it would be fused into.

**Caveat, stated so this is not over-read:** the verdict rests on v1/v2 history.
The v3 voices have exactly **one** paired row each and are graded
`INSUFFICIENT_PAIRED_ROWS` — v3 has not been measured, only v1/v2 have.

### Standing decision

- The panel stays dark. Do not re-arm it on the theory that the cap makes it
  cheap: cheap and negative is still negative.
- `DUMMY_LLM_DAILY_USD_CAP` is now set **explicitly to 1.00** (it had been
  unset, silently riding the 5.00 default, with no spend ledger written yet).
  Explicit and low, but non-zero so a deliberate operator run still works —
  `0` would mean `llm_daily_spend_cap_zero` and refuse everything.
- Revisit only when a voice earns `adds_value_over_fused=true` on **forward**
  evidence. That is now observable: the report runs nightly inside
  `DummyReadinessReport` and lands in `runtime/autonomy/llm_value_report.json`.
