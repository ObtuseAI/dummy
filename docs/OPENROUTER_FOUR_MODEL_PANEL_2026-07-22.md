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
