"""Wave-86: modeled fills may carry stage-1 forward evidence, under an arm.

Auto-promotion required WITNESSED fills, witnessed fills required live trading,
and live trading required auto-promotion. That closed loop is why 45 of 45
candidates were declined and nothing had ever promoted.

Arming ``allow_modeled_fill_evidence`` lets the challenger lane's modeled
taker-at-ask fills satisfy the fill-PROVENANCE flag. It must not loosen
anything about the INDEPENDENCE of the evidence -- cluster counts, span,
bootstrap CI and forward-of-registration all stay -- because those are what
stop one day of 88 correlated SOL 15m fills reading as 88 independent results.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from autonomy.auto_promotion import (
    FORWARD_EVIDENCE_VERSION,
    PromotionConfig,
    forward_witnessed_fill_evidence,
)

REGISTERED = datetime(2026, 7, 1, tzinfo=timezone.utc)
ARMED = PromotionConfig(allow_modeled_fill_evidence=True)
STRICT = PromotionConfig()


def _payload(**overrides):
    """Forward evidence that clears every independence gate."""
    clusters = {f"c{i}": [0.4, 0.5] for i in range(35)}       # 35 clusters / 70 trades
    stamps = [
        (REGISTERED + timedelta(days=1 + (i % 10), hours=i % 24)).isoformat()
        for i in range(70)
    ]
    payload = {
        "evidence_version": FORWARD_EVIDENCE_VERSION,
        "evidence_origin": "ledger_verified",
        "receipt_bounded": True,
        "witnessed_fill_net_pnl": True,
        "out_of_sample_after_registration": True,
        "isolated_candidate_decisions": True,
        "candidate_fingerprint": hashlib.sha256(b"candidate").hexdigest(),
        "registered_at": REGISTERED.isoformat(),
        "n_trades": 70,
        "pnl_by_cluster": clusters,
        "trade_timestamps": stamps,
    }
    payload.update(overrides)
    return {"forward_evidence": payload}


def test_witnessed_evidence_still_passes_and_is_graded_witnessed():
    out = forward_witnessed_fill_evidence("s|a|b|c", _payload(), config=STRICT)
    assert out["pass"] is True
    assert out["evidence_grade"] == "witnessed"


def test_modeled_fills_are_refused_by_default():
    """A fresh clone, CI, and the suite all keep the strict rule."""
    realized = _payload(
        witnessed_fill_net_pnl=False, fill_provenance="modeled_taker_at_ask",
    )
    out = forward_witnessed_fill_evidence("s|a|b|c", realized, config=STRICT)
    assert out["pass"] is False
    assert out["automatic_promotion_authority"] is False
    assert "witnessed_fill_net_pnl" in out["failures"]


def test_modeled_fills_pass_when_armed_and_are_stamped_modeled():
    realized = _payload(
        witnessed_fill_net_pnl=False, fill_provenance="modeled_taker_at_ask",
    )
    out = forward_witnessed_fill_evidence("s|a|b|c", realized, config=ARMED)
    assert out["pass"] is True
    assert out["automatic_promotion_authority"] is True
    # Permanently self-identifying: never re-readable as a witnessed record.
    assert out["evidence_grade"] == "modeled"
    assert out["fill_provenance"] == "modeled_taker_at_ask"
    assert out["witnessed_fill_net_pnl"] is False
    assert out["modeled_fill_evidence_allowed"] is True


def test_arming_does_not_relax_cluster_independence():
    """One cluster of 70 fills must still fail, armed or not."""
    realized = _payload(
        witnessed_fill_net_pnl=False, fill_provenance="modeled",
        pnl_by_cluster={"one_burst": [0.4] * 70},
    )
    out = forward_witnessed_fill_evidence("s|a|b|c", realized, config=ARMED)
    assert out["pass"] is False
    assert "minimum_event_clusters" in out["failures"]


def test_arming_does_not_relax_the_span_requirement():
    """Every fill inside a single day -- the 88-SOL-in-a-day shape."""
    realized = _payload(
        witnessed_fill_net_pnl=False, fill_provenance="modeled",
        trade_timestamps=[
            (REGISTERED + timedelta(days=1, minutes=i)).isoformat() for i in range(70)
        ],
    )
    out = forward_witnessed_fill_evidence("s|a|b|c", realized, config=ARMED)
    assert out["pass"] is False
    assert "minimum_span_days" in out["failures"]


def test_arming_does_not_admit_unregistered_or_backdated_fills():
    """Fills at/before registration are still not forward evidence."""
    realized = _payload(
        witnessed_fill_net_pnl=False, fill_provenance="modeled",
        trade_timestamps=[
            (REGISTERED - timedelta(days=1, minutes=i)).isoformat() for i in range(70)
        ],
    )
    out = forward_witnessed_fill_evidence("s|a|b|c", realized, config=ARMED)
    assert out["pass"] is False
    assert "not_strictly_forward_of_registration" in out["failures"]


def test_arming_does_not_admit_a_non_modeled_provenance():
    """Only an explicitly modeled provenance benefits; junk still fails."""
    realized = _payload(
        witnessed_fill_net_pnl=False, fill_provenance="self_attested",
    )
    out = forward_witnessed_fill_evidence("s|a|b|c", realized, config=ARMED)
    assert out["pass"] is False
    assert "witnessed_fill_net_pnl" in out["failures"]


def test_counter_dict_provenance_is_understood():
    """Real dossiers carry a COUNTER, not a string.

    auto_promotion_runner builds fill_provenance as
    {"modeled_taker": n, "book_witnessed": m}. Comparing that dict to strings
    made the whole concession a silent no-op on live data while every
    string-based fixture passed -- the exact shape of bug this repo keeps
    finding. Both forms must work.
    """
    counter = _payload(
        witnessed_fill_net_pnl=False,
        fill_provenance={"modeled_taker": 70, "book_witnessed": 0},
    )
    assert forward_witnessed_fill_evidence(
        "s|a|b|c", counter, config=STRICT,
    )["pass"] is False
    out = forward_witnessed_fill_evidence("s|a|b|c", counter, config=ARMED)
    assert out["pass"] is True
    assert out["evidence_grade"] == "modeled"

    # A purely book-witnessed counter is not "modeled" and needs no concession.
    witnessed = _payload(fill_provenance={"modeled_taker": 0, "book_witnessed": 70})
    assert forward_witnessed_fill_evidence(
        "s|a|b|c", witnessed, config=STRICT,
    )["evidence_grade"] == "witnessed"


def test_minimal_bar_removes_the_time_gate_but_not_the_ci_gate():
    """Owner directive: no time gates, minimal volume -- but a real edge.

    The single day of fills that the standard bar refuses on span must now
    pass, while a scope whose bootstrap CI lower bound is not strictly
    positive must still fail. That CI is the difference between "this works"
    and "this had a good week", and it is not part of the concession.
    """
    minimal = PromotionConfig(
        allow_modeled_fill_evidence=True, minimal_bar=True,
    )
    one_day = _payload(
        witnessed_fill_net_pnl=False, fill_provenance="modeled",
        trade_timestamps=[
            (REGISTERED + timedelta(days=1, minutes=i)).isoformat() for i in range(70)
        ],
    )
    strict_out = forward_witnessed_fill_evidence("s|a|b|c", one_day, config=ARMED)
    assert strict_out["pass"] is False and "minimum_span_days" in strict_out["failures"]

    out = forward_witnessed_fill_evidence("s|a|b|c", one_day, config=minimal)
    assert out["pass"] is True
    assert out["bar"] == "minimal"
    assert out["minimum_span_days"] == 0.0

    # A flat/negative edge still cannot promote, minimal bar or not.
    flat = _payload(
        witnessed_fill_net_pnl=False, fill_provenance="modeled",
        pnl_by_cluster={f"c{i}": [0.0, 0.0] for i in range(35)},
    )
    flat_out = forward_witnessed_fill_evidence("s|a|b|c", flat, config=minimal)
    assert flat_out["pass"] is False
    assert "positive_cluster_ci95_lower" in flat_out["failures"]


def test_minimal_bar_is_off_unless_separately_armed(monkeypatch):
    """The two concessions arm independently."""
    import importlib

    import autonomy.auto_promotion as mod

    for name in ("DUMMY_PROMOTION_MINIMAL_BAR", "DUMMY_PROMOTION_ALLOW_MODELED_FILLS"):
        monkeypatch.delenv(name, raising=False)
    importlib.reload(mod)
    assert mod.DEFAULT_CONFIG.minimal_bar is False

    monkeypatch.setenv("DUMMY_PROMOTION_MINIMAL_BAR", "1")
    importlib.reload(mod)
    assert mod.DEFAULT_CONFIG.minimal_bar is True
    assert mod.DEFAULT_CONFIG.allow_modeled_fill_evidence is False   # independent

    monkeypatch.delenv("DUMMY_PROMOTION_MINIMAL_BAR", raising=False)
    importlib.reload(mod)


def test_default_config_is_strict_unless_env_armed(monkeypatch):
    """DEFAULT_CONFIG reads the operator arm, and defaults to strict."""
    import importlib

    import autonomy.auto_promotion as mod

    monkeypatch.delenv("DUMMY_PROMOTION_ALLOW_MODELED_FILLS", raising=False)
    importlib.reload(mod)
    assert mod.DEFAULT_CONFIG.allow_modeled_fill_evidence is False

    monkeypatch.setenv("DUMMY_PROMOTION_ALLOW_MODELED_FILLS", "1")
    importlib.reload(mod)
    assert mod.DEFAULT_CONFIG.allow_modeled_fill_evidence is True

    monkeypatch.delenv("DUMMY_PROMOTION_ALLOW_MODELED_FILLS", raising=False)
    importlib.reload(mod)
