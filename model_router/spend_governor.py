"""Enforced daily USD ceiling for paid model calls.

``CostTracker`` observes spend after the fact; nothing ever stopped it.  This
module is the enforcement half: a per-UTC-day budget a paid call must RESERVE
before the provider is contacted.  It is persisted to disk because the daemon
builds a fresh brain -- and therefore a fresh :class:`ModelRouter` -- every
cycle, so an in-process counter would reset several times an hour and never
bind on anything.

The policy:

* RESERVE-THEN-SETTLE.  The estimated price of a call is written to the ledger
  BEFORE the request leaves the process and reconciled against the provider's
  reported cost afterwards.  A crash, a hang, or a provider that reports no
  usage therefore over-counts the day, never under-counts it.
* FAIL-CLOSED.  An unreadable ledger, an unwritable ledger, a non-positive cap,
  a nonsense estimate, or an estimate that would cross the cap all REFUSE the
  call.  The refusal is a reason string the router puts on the envelope, not an
  exception, so callers degrade the way they already do for the closed live
  gate.
* FREE ROUTES STAY FREE.  ``mock`` and the local-CLI panelists (which bill a
  personal subscription, not this budget) never reserve anything, so a dark
  panel or a mock-only suite can never exhaust the day.

Deterministic and injectable (clock, path, cap) so the whole policy is unit
tested without a wall clock or the live runtime directory.

Cross-process note: a reservation is a read-modify-write of one small JSON
file, so two OS processes reserving in the same instant can overshoot by a
single call's estimate.  Within a process the reserve performs no ``await``,
so the asyncio panel fan-out is serialized against itself.
"""
from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from model_router.config import ProviderConfig

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATE_PATH = PROJECT_ROOT / "runtime" / "autonomy" / "llm_spend_budget.json"

# Operator controls, following the repo's DUMMY_* convention.
DAILY_CAP_ENV = "DUMMY_LLM_DAILY_USD_CAP"
STATE_PATH_ENV = "DUMMY_LLM_SPEND_STATE_PATH"
DEFAULT_DAILY_USD_CAP = 5.0

# Fallback list price for a metered route that declares no per-million pricing
# in configs/model_routing.json.  Deliberately the same pessimistic pair the
# provider telemetry falls back to, so a reservation is never cheaper than the
# cost the tracker will later report for the same call.
FALLBACK_PROMPT_COST_PER_MILLION = 1.00
FALLBACK_COMPLETION_COST_PER_MILLION = 5.00
# Coarse and deliberately generous: over-estimating the prompt only makes the
# ceiling bind earlier, which is the safe direction.
CHARS_PER_TOKEN = 4

REASON_CAP_REACHED = "llm_daily_spend_cap_reached"
REASON_CAP_DISABLED = "llm_daily_spend_cap_zero"
REASON_ESTIMATE_INVALID = "llm_spend_estimate_invalid"
REASON_STATE_UNREADABLE = "llm_spend_ledger_unreadable"
REASON_STATE_UNWRITABLE = "llm_spend_ledger_unwritable"

#: Every fallback reason this governor can put on an envelope.  ``CostTracker``
#: uses it to count refusals without re-deriving the string set.
SPEND_CAP_REASONS = frozenset({
    REASON_CAP_REACHED,
    REASON_CAP_DISABLED,
    REASON_ESTIMATE_INVALID,
    REASON_STATE_UNREADABLE,
    REASON_STATE_UNWRITABLE,
})

# Float noise guard: a reservation that lands exactly on the cap is allowed.
_EPSILON = 1e-9


def _default_state_path() -> Path:
    """The ledger to use when neither the caller nor the env names one.

    The live ledger is off-limits to the suite: parts of it open the live gate
    against a mocked transport, and a reservation whose call "fails" is
    deliberately never refunded, so a plain ``pytest`` run would charge the
    operator's real daily budget for calls that never left the process.  That
    isolation is the TEST harness's job, not this module's -- ``tests/
    conftest.py`` points ``DUMMY_LLM_SPEND_STATE_PATH`` at tmp for every test.
    This function deliberately has no way to tell that it is running under a
    test; an earlier version branched on a pytest environment variable, and
    ``test_production_module_has_no_test_awareness`` keeps it from coming back.
    """
    return DEFAULT_STATE_PATH


def _env_float(name: str, default: float) -> float:
    """Non-negative float env override, else *default* (fail-safe on garbage)."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw.strip())
    except (TypeError, ValueError):
        return default
    if not math.isfinite(value) or value < 0.0:
        return default
    return value


def _price(value: float | None, fallback: float) -> float:
    """A configured per-million price, or *fallback* when it is unusable."""
    if value is None:
        return fallback
    try:
        price = float(value)
    except (TypeError, ValueError):
        return fallback
    if not math.isfinite(price) or price < 0.0:
        return fallback
    return price


def is_metered_route(provider_name: str, config: ProviderConfig | None) -> bool:
    """True when contacting *provider_name* spends real USD on this budget.

    ``mock`` is free.  The local-CLI panelists declare no ``api_base`` because
    they shell out to a subscription-billed executable rather than buying
    tokens, so they are outside this ceiling.  An unrecognized route with no
    config at all is assumed to bill (fail-closed).
    """
    name = (provider_name or "").strip().lower()
    if name in ("", "mock", "none"):
        return False
    if config is None:
        return True
    return bool(str(config.api_base or "").strip())


def estimate_call_cost_usd(
    config: ProviderConfig | None, prompt: str, max_tokens: int
) -> float:
    """Worst-case USD price of one call, priced from the route's list prices.

    Completion tokens are charged at the full ``max_tokens`` the caller asked
    for: the reservation must cover the most expensive answer the provider is
    allowed to return.
    """
    prompt_price = FALLBACK_PROMPT_COST_PER_MILLION
    completion_price = FALLBACK_COMPLETION_COST_PER_MILLION
    if config is not None:
        prompt_price = _price(
            config.prompt_cost_per_million, FALLBACK_PROMPT_COST_PER_MILLION)
        completion_price = _price(
            config.completion_cost_per_million, FALLBACK_COMPLETION_COST_PER_MILLION)
    prompt_tokens = math.ceil(max(len(prompt or ""), 0) / CHARS_PER_TOKEN)
    try:
        completion_tokens = max(int(max_tokens), 0)
    except (TypeError, ValueError):
        completion_tokens = 0
    estimate = (
        prompt_tokens * prompt_price + completion_tokens * completion_price
    ) / 1_000_000
    return round(max(estimate, 0.0), 8)


@dataclass(frozen=True)
class SpendState:
    """The persisted per-UTC-day ledger."""

    day: str
    spent_usd: float
    calls: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "spent_usd": round(self.spent_usd, 8),
            "calls": int(self.calls),
        }


@dataclass(frozen=True)
class SpendDecision:
    """The answer to "may this paid call happen?", safe to log or serialize."""

    allowed: bool
    reason: str | None
    reserved_usd: float
    spent_usd: float
    cap_usd: float
    day: str

    @property
    def remaining_usd(self) -> float:
        return round(max(self.cap_usd - self.spent_usd, 0.0), 6)

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "reserved_usd": round(self.reserved_usd, 8),
            "spent_usd": round(self.spent_usd, 8),
            "cap_usd": round(self.cap_usd, 6),
            "remaining_usd": self.remaining_usd,
            "day": self.day,
        }


class LlmSpendGovernor:
    """Enforce a daily USD ceiling across process-per-cycle model routers."""

    def __init__(
        self,
        *,
        daily_usd_cap: float | None = None,
        state_path: Path | None = None,
        now_fn: Callable[[], float] | None = None,
    ) -> None:
        cap = (
            float(daily_usd_cap) if daily_usd_cap is not None
            else _env_float(DAILY_CAP_ENV, DEFAULT_DAILY_USD_CAP)
        )
        # A nonsense explicit cap closes the door rather than opening it.
        self.daily_usd_cap = cap if math.isfinite(cap) and cap > 0.0 else 0.0
        env_path = os.environ.get(STATE_PATH_ENV)
        if state_path is not None:
            self.state_path = Path(state_path)
        elif env_path:
            self.state_path = Path(env_path)
        else:
            self.state_path = _default_state_path()
        self._now = now_fn or time.time

    # -- clock -----------------------------------------------------------------

    def _day_key(self) -> str:
        return time.strftime("%Y-%m-%d", time.gmtime(self._now()))

    # -- ledger ----------------------------------------------------------------

    def _load(self) -> tuple[SpendState | None, str | None]:
        """``(state, None)`` or ``(None, reason)`` when the ledger is untrusted.

        A ledger that cannot be read is NOT treated as an empty day: silently
        restarting the count is exactly how a corrupt file would buy unlimited
        calls.
        """
        day = self._day_key()
        try:
            exists = self.state_path.exists()
        except OSError:
            return None, REASON_STATE_UNREADABLE
        if not exists:
            return SpendState(day=day, spent_usd=0.0, calls=0), None
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None, REASON_STATE_UNREADABLE
        if not isinstance(raw, dict):
            return None, REASON_STATE_UNREADABLE
        try:
            state = SpendState(
                day=str(raw.get("day") or day),
                spent_usd=float(raw.get("spent_usd", 0.0)),
                calls=int(raw.get("calls", 0)),
            )
        except (TypeError, ValueError):
            return None, REASON_STATE_UNREADABLE
        if not math.isfinite(state.spent_usd) or state.spent_usd < 0.0:
            return None, REASON_STATE_UNREADABLE
        if state.day != day:
            # UTC rollover: the new day starts clean.
            return SpendState(day=day, spent_usd=0.0, calls=0), None
        return state, None

    def _save(self, state: SpendState) -> bool:
        """Atomically replace the ledger.  False means the write failed."""
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.state_path.with_name(self.state_path.name + ".tmp")
            tmp.write_text(
                json.dumps(state.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
            os.replace(tmp, self.state_path)
            return True
        except OSError:
            return False

    # -- public surface --------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """Redacted, JSON-safe view of today's budget."""
        state, error = self._load()
        if state is None:
            return {
                "day": self._day_key(),
                "cap_usd": round(self.daily_usd_cap, 6),
                "spent_usd": None,
                "remaining_usd": 0.0,
                "calls": 0,
                "error": error,
                "enforced": True,
            }
        return {
            "day": state.day,
            "cap_usd": round(self.daily_usd_cap, 6),
            "spent_usd": round(state.spent_usd, 8),
            "remaining_usd": round(max(self.daily_usd_cap - state.spent_usd, 0.0), 6),
            "calls": state.calls,
            "error": None,
            "enforced": True,
        }

    def reserve(self, estimate_usd: float) -> SpendDecision:
        """Charge *estimate_usd* to today's budget before the call is made."""
        cap = self.daily_usd_cap
        day = self._day_key()
        try:
            amount = float(estimate_usd)
        except (TypeError, ValueError):
            return SpendDecision(False, REASON_ESTIMATE_INVALID, 0.0, 0.0, cap, day)
        if not math.isfinite(amount) or amount < 0.0:
            return SpendDecision(False, REASON_ESTIMATE_INVALID, 0.0, 0.0, cap, day)

        state, error = self._load()
        if state is None:
            return SpendDecision(False, error, 0.0, 0.0, cap, day)
        if cap <= 0.0:
            return SpendDecision(
                False, REASON_CAP_DISABLED, 0.0, state.spent_usd, cap, state.day)
        if state.spent_usd + amount > cap + _EPSILON:
            return SpendDecision(
                False, REASON_CAP_REACHED, 0.0, state.spent_usd, cap, state.day)

        reserved = SpendState(
            day=state.day,
            spent_usd=round(state.spent_usd + amount, 8),
            calls=state.calls + 1,
        )
        if not self._save(reserved):
            # An unrecorded call is an unbounded call.
            return SpendDecision(
                False, REASON_STATE_UNWRITABLE, 0.0, state.spent_usd, cap, state.day)
        return SpendDecision(
            True, None, amount, reserved.spent_usd, cap, reserved.day)

    def settle(self, decision: SpendDecision | None, actual_usd: float | None) -> None:
        """Reconcile a reservation with the provider's reported cost.

        Only a credible reported cost moves the ledger.  ``None`` -- a failed
        call, or a provider that reports no usage -- leaves the estimate
        standing, because a request that left the process may have been billed
        whether or not it came back.
        """
        if decision is None or not decision.allowed or actual_usd is None:
            return
        try:
            actual = float(actual_usd)
        except (TypeError, ValueError):
            return
        if not math.isfinite(actual) or actual < 0.0:
            return
        delta = actual - decision.reserved_usd
        if abs(delta) < _EPSILON:
            return
        state, _error = self._load()
        if state is None or state.day != decision.day:
            # Untrusted ledger, or the day rolled over mid-call: never rewrite
            # a day this reservation does not belong to.
            return
        self._save(SpendState(
            day=state.day,
            spent_usd=max(0.0, round(state.spent_usd + delta, 8)),
            calls=state.calls,
        ))
