"""Property-style invariant sweeps (Jane Street discipline, seeded + deterministic).

Example-based tests prove points; these sweep thousands of randomized inputs
through the fail-closed core and assert the INVARIANTS hold universally:
fees, tier-snapshot tamper evidence, genome clamps, crossover closure, rest
shift bounds, prop pricing bounds, provenance ordering.
"""
from __future__ import annotations

import random

SEED = 20260723
N = 2000


def test_kalshi_taker_fee_bounds_and_scaling():
    from autonomy.fees import kalshi_taker_fee_cents

    rng = random.Random(SEED)
    for _ in range(N):
        price = rng.randint(1, 99)
        count = rng.randint(1, 50)
        fee = kalshi_taker_fee_cents(price, count, "KXBTC1H-26JUL231500-15")
        assert fee >= 0
        assert fee <= 100 * count  # fee can never exceed max contract value
        # More contracts never cost less in fees.
        assert kalshi_taker_fee_cents(price, count + 1, "KXBTC1H-X") >= fee


def test_tier_snapshot_digest_detects_any_field_tamper():
    from autonomy.tier_policy import _tier_snapshot_digest

    rng = random.Random(SEED)
    base = {
        "tier": "B", "tier_side": "yes", "tier_after_fee_edge": 0.031,
        "tier_entry_price_cents": 44, "tier_scope": "MLB",
        "tier_reason": "meets_b_edge_and_uncertainty",
    }
    original = _tier_snapshot_digest(base)
    for _ in range(500):
        tampered = dict(base)
        key = rng.choice(list(base))
        if isinstance(base[key], (int, float)):
            tampered[key] = base[key] + rng.choice([1, -1, 7])
        else:
            tampered[key] = str(base[key]) + "x"
        assert _tier_snapshot_digest(tampered) != original


def test_bounded_genome_clamp_is_total_and_idempotent():
    from autonomy.evolution_lab import _bounded_genome

    rng = random.Random(SEED)
    for _ in range(N):
        genome = _bounded_genome(
            rng.uniform(-5, 5), rng.randint(-50, 80),
            rng.uniform(-2, 2), rng.randint(-100, 300),
        )
        assert genome.is_bounded()
        again = _bounded_genome(
            genome.shrinkage, genome.edge_threshold_cents,
            genome.max_uncertainty, genome.max_entry_price_cents,
        )
        assert again == genome  # clamping a clamped genome changes nothing


def test_crossover_closure_and_determinism():
    from autonomy.evolution_lab import ResearchGenome, crossover_genomes, _bounded_genome

    rng = random.Random(SEED)
    for _ in range(500):
        a = _bounded_genome(rng.uniform(0, 2), rng.randint(0, 30),
                            rng.uniform(0, 1), rng.randint(30, 120))
        b = _bounded_genome(rng.uniform(0, 2), rng.randint(0, 30),
                            rng.uniform(0, 1), rng.randint(30, 120))
        children = crossover_genomes(a, b)
        assert all(isinstance(c, ResearchGenome) and c.is_bounded() for c in children)
        assert crossover_genomes(a, b) == children


def test_rest_shift_always_bounded_and_sign_correct():
    from autonomy.sports.rest import MAX_REST_LOGIT_SHIFT, apply_rest_shift, rest_logit_shift

    rng = random.Random(SEED)
    for _ in range(N):
        home = rng.uniform(0, 20)
        away = rng.uniform(0, 20)
        coeff = rng.uniform(0, 0.5)
        shift = rest_logit_shift(home, away, coeff)
        assert abs(shift) <= MAX_REST_LOGIT_SHIFT + 1e-12
        if home > away:
            assert shift >= 0
        if home < away:
            assert shift <= 0
        p = apply_rest_shift(rng.uniform(0.001, 0.999), shift)
        assert 0.02 <= p <= 0.98


def test_prop_over_probability_bounds_and_monotonicity():
    from autonomy.sports.player_props import prop_over_probability

    rng = random.Random(SEED)
    for _ in range(N):
        mean = rng.uniform(0.5, 60)
        sigma = rng.uniform(0.5, 20)
        line = rng.uniform(0.5, 60)
        p = prop_over_probability(mean, sigma, line)
        assert p is not None and 0.0 <= p <= 1.0
        # Higher mean at the same line never lowers the over probability.
        p2 = prop_over_probability(mean + 1.0, sigma, line)
        assert p2 >= p - 1e-12


def test_retro_provenance_ordering_invariant():
    from datetime import datetime, timedelta, timezone
    from autonomy.ingest.provenance import stamp_retro_source_reported

    rng = random.Random(SEED)
    now = datetime(2026, 7, 23, tzinfo=timezone.utc)
    for _ in range(500):
        start = now - timedelta(days=rng.uniform(1, 4000))
        row = {
            "game_id": "g", "status": "final",
            "home_score": rng.randint(0, 20), "away_score": rng.randint(0, 20),
            "start_time": start.isoformat(),
        }
        stamped = stamp_retro_source_reported([row], now=now)
        if stamped:
            available = datetime.fromisoformat(row["result_available_at"])
            received = datetime.fromisoformat(row["received_at"])
            # The strict lake ordering must hold by construction.
            assert start <= available <= received
