# Cross-candidate allocation — dividing the pot by demonstrated calibration

**Date:** 2026-07-24
**Status:** design approved, not implemented
**Scope:** how a capped budget is divided among simultaneously-qualifying candidates

## Problem

Nothing in DUMMY divides a budget across the candidate set. Allocation today is greedy,
order-dependent, and blind to how many candidates exist.

Three concrete defects:

**1. Ranking ignores demonstrated accuracy.** `autonomy/brain.py:873` sorts candidates by
`edge_velocity` — *estimated* edge per unit of settlement time. That ranking has no input
from how the scope has actually graded. A scope with a fat estimated edge and poor
calibration outranks a modest edge from a scope that reliably beats the line.

**2. The first candidate takes the whole pot.** `autonomy/allocator.py:223`:

```python
count = budget.max_notional_cents // price
```

`budget.max_notional_cents` is the *entire remaining* budget permitted by the stage and
Kelly caps. The top-ranked candidate consumes what it can, and everything below it competes
for the remainder. A candidate ranked second by a hair can receive nothing.

**3. N is never counted.** Forty qualifying candidates and three qualifying candidates
produce identical per-candidate sizing. There is no thinning as breadth grows.

`autonomy/risk_brain.py` already sizes a *single* order well — quarter-Kelly, stage ladder,
drawdown ladder, correlation-group caps. The missing piece is strictly the cross-candidate
step.

## Non-goals

- **`configs/caps.json` is not touched.** It stays byte-sealed under `PROTECTED_CAPS_SHA256`.
  This design changes only how budget is divided *inside* existing caps.
- **No change to what qualifies.** Entry thresholds, EV floors, tier gates and the live
  firewall are untouched. This decides size, not eligibility.
- **No new evidence source.** Weights come from calibration metrics that already exist.

## Architecture

Today the decision path is one pass: rank, then each candidate takes what it can. It becomes
two passes with a pure function between them.

```
scored candidates
      |
      v
[ Pass 1: ASK ]      existing allocator logic, unchanged, up to
                     budget.max_notional_cents -- but that number is now a
                     REQUEST, not a grant
      |
      v
[ allocate() ]       pure, no I/O: weights x policy x pot -> per-candidate cents
      |
      v
[ Pass 2: GRANT ]    count = min(allocated, budget.max_notional_cents) // price
      |
      v
risk_brain.order_budget -> live firewall -> order
```

The allocator sits *before* every existing control and can only ever reduce a size. Pass 2
takes a `min` against the same budget Pass 1 asked from, so no allocation can exceed what
the risk brain already permitted.

### The pot

`pot_cents` is the budget available to the whole candidate set for this cycle:

```
pot_cents = floor(throttle * remaining_total_exposure_cents)
```

where `remaining_total_exposure_cents` is the stage's total-exposure allowance less
currently open exposure — the same quantity `risk_brain` already derives from
`STAGE_LIMITS[stage]["total_frac"]` and live bankroll, further bounded on the live path by
`max_total_live_exposure_cents` from the sealed caps.

The pot is therefore never a new number. It is the existing remaining-exposure headroom,
optionally shrunk by the operator throttle. `throttle` is applied once, here, and nowhere
else.

## Component: `autonomy/candidate_allocation.py`

Pure module. No filesystem, no clock, no network, no state.

```python
@dataclass(frozen=True)
class Ask:
    candidate_id: str
    scope: str              # source|subject|market_type|horizon
    ask_cents: int          # budget.max_notional_cents from pass 1
    price_cents: int

@dataclass(frozen=True)
class Grant:
    candidate_id: str
    granted_cents: int
    weight: float
    policy: str
    reason: str             # why this number, for the board and the tote app

def allocate(
    asks: Sequence[Ask],
    pot_cents: int,
    weights: Mapping[str, float],   # scope -> weight, already resolved
    policy: AllocationPolicy,
) -> list[Grant]
```

Keeping weight *resolution* out of `allocate()` is deliberate: the split rule is then
testable without any calibration fixtures.

### Policies

| policy | rule | deploys full pot |
|---|---|---|
| `kelly_prorata` **(default)** | `raw_i = ask_i * w_i`; if `Σraw > pot`, scale every grant by `pot/Σraw` | no |
| `proportional` | `grant_i = w_i / Σw * pot`, then clamped to `ask_i` | yes, until clamps bind |
| `top_k` | rank by `w_i`, fund the top K at `ask_i`, rest get zero | up to K |

`kelly_prorata` under-deploys on thin nights by design. Two good edges do not get inflated
because nothing else showed up — Kelly already answered how much those two are worth, and
padding them out to fill the pot would size on availability rather than on edge.

`proportional` clamps each share to `ask_i` and does **not** redistribute the remainder. A
single pass keeps the rule explainable in the app; redistribution would turn it into an
iterative water-filling algorithm whose result nobody can predict by eye.

## Weights

Driven by **contested Brier advantage** — how much better the model's Brier is than the
market's own price on the same rows. `autonomy/scope_analytics.py:261`:

```python
brier_edge = market_brier - model_brier_contested   # positive => model beat the line
```

Weight uses the **lower 95% bound**, not the point estimate:
`contested_brier_advantage_lower95` (`autonomy/backtest.py:1164`), which the promotion gate
already tests for `> 0` (`backtest.py:1180`). A scope with twelve lucky samples must not
size up on a point estimate its sample size cannot support.

```
adv_i = contested_brier_advantage_lower95 for scope i
w_i   = clamp(min_weight, 1.0, adv_i / target_advantage)
```

- `adv_i` missing, or the scope is too thin to have a bound → `w_i = min_weight`
- `adv_i <= 0` → `w_i = min_weight`

`min_weight` is a floor, never zero. A scope that cannot receive any allocation can never
settle, never accrue evidence, and never earn a higher weight — a zero floor is an
absorbing state that permanently freezes new scopes out. Eligibility is the job of the
existing promotion and tier gates; this layer only sizes what those gates already passed.

Equally, an unproven scope must not start at `1.0`. Unproven is not proven.

## Operator control

`configs/allocation.json`, following `autonomy/switches.py` exactly: file is source of
truth, per-key env var overrides it, read fresh every cycle, nothing cached across fires.

| key | default | meaning |
|---|---|---|
| `policy` | `kelly_prorata` | one of the three rules |
| `top_k` | `5` | only read when `policy` is `top_k` |
| `min_weight` | `0.25` | weight floor for unproven or negative-advantage scopes |
| `target_advantage` | `0.02` | contested-Brier advantage that earns full weight |
| `throttle` | `1.0` | scales the whole pot; one dial to pull without touching anything else |

Env overrides: `DUMMY_ALLOC_POLICY`, `DUMMY_ALLOC_TOP_K`, `DUMMY_ALLOC_MIN_WEIGHT`,
`DUMMY_ALLOC_TARGET_ADVANTAGE`, `DUMMY_ALLOC_THROTTLE`.

### Fail-safe direction differs from switches.py

`switches.py` fails **all-on**, because a corrupt file must not silently stop trading. This
file fails to **`kelly_prorata` at stock defaults** — a corrupt file must never read as
"deploy everything." The two modules share a pattern but not a failure direction, and the
difference is deliberate.

`throttle` is clamped to `[0.0, 1.0]`. It can only shrink the pot. There is no operator
value that enlarges it; enlarging requires the sealed-caps ceremony.

### Dummy Tote

The tote app already writes `configs/switches.json` through its switch toggles, and
`desktop/dummy_tote/data.py` stays pure/read-only for everything else. Allocation control
follows that same split: a small write surface for these five keys, read-only for the
resulting grants. The app shows the active policy, the throttle, and per-candidate
`granted_cents` with its `weight` and `reason`, so a shrunken size is never mysterious.

## Failure modes

| condition | behaviour |
|---|---|
| no calibration data at all | every weight = `min_weight` → near-equal split; the honest "we don't know yet" answer |
| config unreadable / malformed | stock defaults, `kelly_prorata` |
| `pot_cents <= 0` | no grants |
| `Σw == 0` | unreachable while `min_weight > 0`; defensively returns no grants |
| `policy` unrecognized | `kelly_prorata`, and the unknown value is reported on the board |
| `ask_i <= 0` | candidate excluded before weighting |
| rounding leaves a residual cent | dropped, never redistributed — `Σ granted ≤ pot` is the invariant that must not bend |

## Testing

`allocate()` is pure, so these are property tests over generated inputs, not fixtures:

1. `Σ granted_cents <= pot_cents` — for every policy, every input
2. `granted_i <= ask_i` — the allocator never raises a size
3. **monotone thinning:** adding a candidate never increases any existing candidate's grant
4. **weight monotonicity:** raising one scope's weight, all else equal, does not decrease its
   grant
5. switching policy changes distribution only — invariants 1 and 2 hold across all three
6. unknown scope resolves to exactly `min_weight` — never `0.0`, never `1.0`
7. `throttle=0.0` grants nothing; `throttle=1.0` is identical to no throttle
8. determinism: identical inputs produce identical grants (ties broken on `candidate_id`, not
   dict order)

Integration tests: a cycle with N candidates and a fixed pot produces `Σ notional ≤` the
existing caps, and no existing firewall or risk-brain test changes behaviour.

## Risks

**Calibration lags reality.** Contested Brier is backward-looking. A scope that degrades
gets full weight until enough new rows settle. The drawdown ladder in `risk_brain` remains
the fast-reacting brake; this layer is the slow, earned one. They are different jobs and
both stay on.

**Concentration via weight.** With few candidates and one high-weight scope,
`kelly_prorata` can put most of the pot in one place. Existing per-market, per-group and
correlation caps still bind, so this cannot become a single undiversified bet — but the
board should surface the realized concentration so it is visible rather than inferred.

**Tie-breaking on `top_k`.** Ranking by weight alone produces ties at the `min_weight`
floor, where many unproven scopes are identical. Ties break on `candidate_id` for
determinism, which is arbitrary but stable. `top_k` is not the default for this reason.
