# Correction — the series grant the brain never read

**Date:** 2026-07-25 (Wave-89)
**Code corrected:** `autonomy/brain.py` `_authoritative_live_candidate_allowlist`
**Authorization:** none required. This grants no authority; it makes the brain honor
the series authorization the operator already registered on 2026-07-25 against caps
`83FCE350…`.
**Capital effect:** none yet. Live submission remains disabled; the operator env gate
and live session are both absent.

## Summary

Wave-88 concluded that positive market authorization was "literally inexpressible"
for contracts that rotate every fifteen minutes, added `CapConfig.allowed_series`
and `market_is_allowlisted()`, registered `allowed_series: ["KXSOL15M"]`, and
recorded the result as **"This is what actually blocked live."**

The new authority was wired into the firewall's deny gate only. The brain's own
upstream live-candidate filter still read `allowed_markets` — the exact-match list
Wave-88 had just established could not express the grant, and which the shipped
caps deliberately leave empty.

Net effect: arming a live session would have scanned zero markets and placed
nothing, indefinitely. The firewall stood ready to accept a `KXSOL15M` order that
the brain could never propose.

## The two allowlists

`live_firewall/firewall.py:43` — enforced in `evaluate()` and again in `submit()`
against the trusted orderbook:

```python
if market_ticker in (getattr(caps, "allowed_markets", None) or []):
    return True
allowed_series = getattr(caps, "allowed_series", None) or []
...
series = market_ticker.split("-", 1)[0]
return series in allowed_series
```

`autonomy/brain.py:197` before this correction — the gate that decides what a LIVE
cycle is even allowed to look at:

```python
raw = load_caps().allowed_markets   # allowed_series never consulted
...
return frozenset(values)
```

and at the call site (`brain.py:862`):

```python
markets = [m for m in markets if live_allowlist is not None and m.ticker in live_allowlist]
```

With `allowed_markets: []` that comprehension is unconditionally empty.

## Why the suite was green

The behavior was pinned, not overlooked. `tests/test_target_execution_integrity.py`
asserted that an empty or unavailable allowlist yields `markets_scanned == 0` — correct
and still asserted — and its loader test monkeypatched a caps object with **no
`allowed_series` attribute at all**, so no test could observe the omission. Wave-88's
own series tests (`tests/test_firewall_series_allowlist.py`) exercised the firewall
matcher directly and never went through the brain.

Two allowlist implementations, each independently tested, with no test spanning both.

## The correction

`_authoritative_live_candidate_allowlist` now returns a predicate backed by the
firewall's own `market_is_allowlisted`, so candidacy and the deny gate cannot drift.
Every fail-closed property is preserved and still tested:

- invalid caps authority → `None` → zero candidates
- malformed entry in **either** grant list (non-string, empty, padded, duplicated)
  → `None` → zero candidates
- caps payload predating `allowed_series` → exact-match only
- boundary-aware series matching — `KXSOL15M` does not authorize `KXSOL15MEGA`
- candidacy is not authority: absent the operator gates the firewall still refuses

New coverage: `test_live_candidacy_honors_a_whole_series_grant`,
`test_live_candidacy_matches_the_firewall_it_will_be_checked_against` (asserts the
two agree ticker for ticker), `test_live_cycle_scans_a_series_authorized_rotating_contract`.

Suite: 7919 passed, 1 skipped (baseline 7916 + 3).

## Pattern

This is the third instance of the same failure in three waves, and worth naming.

Wave-87: an arm-check dictionary computed `True` from config presence, so
`SUBMITTED_..._REAL_BROKER_ATTEMPT` coexisted with `broker_order_id: null`.
Wave-88: a candidate claimed tradability it had never observed, and never expired.
Wave-89: an authorization was granted, registered, tested, and documented as
unblocking live — while the gate that consumes it was never repointed.

Each time the artifact asserted a fact about the world that no code path
established. The check that catches this class is not another unit test; it is
tracing the claim to the line that acts on it. `market_is_allowlisted` had exactly
one caller before this correction, and it was not the brain.
