"""Mined candidates auto-register and accrue strictly-forward evidence."""
from __future__ import annotations

import json

from autonomy.strategy_miner import (
    MinedRow,
    rule_from_spec,
    update_mined_rule_forward_registry,
)


SPEC = [{"feature": "setup_score", "op": ">", "threshold": 0.5}]


def _row(ticker: str, created_at: str, setup: float, edge_sign: int) -> MinedRow:
    # result chosen so brier edge sign is controlled: prob 0.9 vs market 0.5.
    result = edge_sign > 0
    return MinedRow(
        source="crypto_ta",
        ticker=ticker,
        event_cluster=ticker.rsplit("-", 1)[0],
        created_at=created_at,
        probability_yes=0.9 if result else 0.9,
        market_probability=0.5,
        result_yes=result,
        features={"setup_score": setup},
    )


def _report(verdict: str = "candidate") -> dict:
    return {"rules": [{
        "rule": "setup_score > 0.5",
        "rule_spec": SPEC,
        "verdict": verdict,
        "test_brier_edge": 0.02,
    }]}


def test_candidate_registers_once_and_never_redates(tmp_path):
    path = tmp_path / "registry.json"
    first = update_mined_rule_forward_registry(
        [], _report(), now_iso="2026-07-22T00:00:00+00:00", path=path,
    )
    (entry,) = first["rules"].values()
    assert entry["registered_at"] == "2026-07-22T00:00:00+00:00"
    again = update_mined_rule_forward_registry(
        [], _report(), now_iso="2026-07-23T00:00:00+00:00", path=path,
    )
    (entry2,) = again["rules"].values()
    assert entry2["registered_at"] == "2026-07-22T00:00:00+00:00"
    assert again["authority"]["adoption"] == "explicit_governance_action_only"


def test_forward_evidence_counts_only_post_registration_matches(tmp_path):
    path = tmp_path / "registry.json"
    update_mined_rule_forward_registry(
        [], _report(), now_iso="2026-07-22T00:00:00+00:00", path=path,
    )
    rows = [
        # Before registration: ignored even though it matches.
        _row("KXE-A-T1", "2026-07-21T10:00:00+00:00", 0.9, +1),
        # After registration, matching.
        _row("KXE-B-T1", "2026-07-22T10:00:00+00:00", 0.9, +1),
        _row("KXE-C-T1", "2026-07-22T11:00:00+00:00", 0.9, +1),
        # After registration, NOT matching the rule.
        _row("KXE-D-T1", "2026-07-22T12:00:00+00:00", 0.1, +1),
    ]
    document = update_mined_rule_forward_registry(
        rows, {"rules": []}, now_iso="2026-07-23T00:00:00+00:00", path=path,
    )
    (entry,) = document["rules"].values()
    assert entry["forward"]["n_rows"] == 2
    assert entry["forward"]["n_clusters"] == 2
    assert entry["status"] == "TRACKING"  # < 20 clusters never concludes


def test_rejected_rules_are_not_registered(tmp_path):
    path = tmp_path / "registry.json"
    document = update_mined_rule_forward_registry(
        [], _report(verdict="rejected"), now_iso="2026-07-22T00:00:00+00:00",
        path=path,
    )
    assert document["rules"] == {}


def test_rule_from_spec_round_trips():
    rule = rule_from_spec(SPEC)
    good = _row("KXE-A-T1", "2026-07-22T00:00:01+00:00", 0.9, +1)
    bad = _row("KXE-A-T2", "2026-07-22T00:00:01+00:00", 0.1, +1)
    assert rule.matches(good) is True
    assert rule.matches(bad) is False


def test_registry_file_is_valid_json_with_authority_block(tmp_path):
    path = tmp_path / "registry.json"
    update_mined_rule_forward_registry(
        [], _report(), now_iso="2026-07-22T00:00:00+00:00", path=path,
    )
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["authority"]["execution"] is False
    assert document["authority"]["fusion_membership"] is False
