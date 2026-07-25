"""A proof candidate's tradability claim expires.

`_candidate_invariants` checked eight properties and not one of them was
`created_at`. So the canonical candidate on the live box -- validated
2026-07-08, for a market that now returns 404 -- passed every gate, because
`market_tradable: True` was true when it was written and nothing asked when
that was.

Market tradability is a point-in-time observation. Treating a 17-day-old
observation as current is how a live proof gets spent on a delisted market and
records the result as a broker rejection.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.proof_authority import CANDIDATE_MAX_AGE_SECONDS, _candidate_invariants

NOW = datetime(2026, 7, 25, 4, 0, 0, tzinfo=timezone.utc)


def _candidate(created_at, **overrides):
    base = {
        "candidate_found": True,
        "market_tradable": True,
        "contract_tradable": True,
        "price_validated": True,
        "order_type": "LIMIT",
        "count": 1,
        "submit_allowed_now": False,
        "requires_new_operator_proof_authority": True,
        "created_at": created_at,
    }
    base.update(overrides)
    return base


def _iso(dt):
    return dt.isoformat()


class TestFreshCandidatePasses:
    def test_just_validated_passes(self):
        ok, reason = _candidate_invariants(
            _candidate(_iso(NOW - timedelta(seconds=30))), now=NOW)
        assert ok is True, reason
        assert reason == ""

    def test_inside_the_window_passes(self):
        age = CANDIDATE_MAX_AGE_SECONDS - 60
        ok, reason = _candidate_invariants(
            _candidate(_iso(NOW - timedelta(seconds=age))), now=NOW)
        assert ok is True, reason


class TestStaleCandidateBlocks:
    def test_the_real_canonical_candidate_would_be_blocked(self):
        """The exact case from the live box: validated 2026-07-08, market 404s."""
        ok, reason = _candidate_invariants(
            _candidate("2026-07-08T07:11:17.162647+00:00"), now=NOW)
        assert ok is False
        assert reason == "BLOCKED_CANDIDATE_STALE"

    def test_just_outside_the_window_blocks(self):
        age = CANDIDATE_MAX_AGE_SECONDS + 60
        ok, reason = _candidate_invariants(
            _candidate(_iso(NOW - timedelta(seconds=age))), now=NOW)
        assert ok is False
        assert reason == "BLOCKED_CANDIDATE_STALE"


class TestFailsClosed:
    def test_missing_created_at_blocks(self):
        candidate = _candidate(None)
        del candidate["created_at"]
        ok, reason = _candidate_invariants(candidate, now=NOW)
        assert ok is False
        assert reason == "BLOCKED_CANDIDATE_STALE"

    def test_unparseable_created_at_blocks(self):
        ok, reason = _candidate_invariants(_candidate("last tuesday"), now=NOW)
        assert ok is False
        assert reason == "BLOCKED_CANDIDATE_STALE"

    def test_naive_timestamp_blocks_rather_than_guessing_a_zone(self):
        ok, reason = _candidate_invariants(_candidate("2026-07-25T03:59:00"), now=NOW)
        assert ok is False
        assert reason == "BLOCKED_CANDIDATE_STALE"

    def test_future_timestamp_blocks(self):
        ok, reason = _candidate_invariants(
            _candidate(_iso(NOW + timedelta(hours=1))), now=NOW)
        assert ok is False
        assert reason == "BLOCKED_CANDIDATE_STALE"


class TestExistingInvariantsStillApply:
    def test_untradable_market_still_blocks_even_when_fresh(self):
        ok, reason = _candidate_invariants(
            _candidate(_iso(NOW), market_tradable=False), now=NOW)
        assert ok is False
        assert reason == "BLOCKED_MARKET_NOT_TRADABLE"

    def test_null_tradability_blocks_even_when_fresh(self):
        """Wave-88 made unobserved tradability null; null must not pass."""
        ok, reason = _candidate_invariants(
            _candidate(_iso(NOW), market_tradable=None), now=NOW)
        assert ok is False
        assert reason == "BLOCKED_MARKET_NOT_TRADABLE"

    def test_freshness_is_checked_before_nothing_else_regresses(self):
        ok, reason = _candidate_invariants(
            _candidate(_iso(NOW), count=2), now=NOW)
        assert ok is False
        assert reason == "BLOCKED_COUNT_NOT_ONE"
