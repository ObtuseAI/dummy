from __future__ import annotations

import ast
import copy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys

import pytest

from dummy.agents import AgentVertical
from dummy.chronos import ClockDomain
from dummy.organisms import (
    EpisodeRequest,
    EpisodeArtifact,
    EpisodeValidationError,
    HeldOutCase,
    InMemoryEpisodeLedger,
    IssuedEpisodeArtifact,
    IssueRequest,
    JsonlEpisodeLedger,
    PointInTimeEvidence,
    VerifiedSettlement,
    artifact_bytes,
    complete_issued_episode,
    issue_episode,
    run_complete_episode,
    verify_deterministic_replay,
)


NOW = datetime(2026, 7, 14, 22, 0, tzinfo=timezone.utc)


def _held_out_cases() -> tuple[HeldOutCase, ...]:
    return tuple(
        HeldOutCase(
            case_id=f"held-out-{index}",
            event_cluster_id=f"held-out-cluster-{index}",
            market_prior_probability=0.50,
            incumbent_probability=0.68,
            result_yes=True,
            evidence_ids=(f"held-out-settlement-{index}",),
            settlement_source_reference=f"fixture://held-out/{index}",
            settlement_verified=True,
        )
        for index in range(1, 6)
    )


def _request(
    *,
    sport: bool = False,
    incumbent_probability: float | None = None,
    incumbent_uncertainty: float = 0.08,
    future_receipt: bool = False,
) -> EpisodeRequest:
    if sport:
        market_id = "KXMLBGAME-26JUL14CHCATL-CHI"
        market_type = "winner"
        vertical = AgentVertical.MLB
        clock = ClockDomain.PREGAME
        bid, ask, no_bid, no_ask = 44, 46, 54, 56
        probability = incumbent_probability if incumbent_probability is not None else 0.65
        objective = "Forecast the MLB pregame winner without replacing the incumbent"
    else:
        market_id = "KXBTC15M-26JUL142215-15"
        market_type = "15m_direction"
        vertical = AgentVertical.CRYPTO
        clock = ClockDomain.FIFTEEN_MINUTE
        bid, ask, no_bid, no_ask = 49, 51, 49, 51
        probability = incumbent_probability if incumbent_probability is not None else 0.70
        objective = "Forecast BTC direction for the next 15 minutes"
    close = NOW + timedelta(minutes=15)
    received = NOW + timedelta(seconds=1) if future_receipt else NOW
    evidence = (
        PointInTimeEvidence(
            evidence_id=f"quote-{market_id}",
            source_family="kalshi-public-book",
            observed_at=NOW - timedelta(seconds=1),
            received_at=received,
            source_reference=f"fixture://quotes/{market_id}",
            observed_at_verified=True,
            received_at_verified=True,
            payload={
                "kind": "market_quote",
                "market_id": market_id,
                "status": "open",
                "yes_bid": bid,
                "yes_ask": ask,
                "no_bid": no_bid,
                "no_ask": no_ask,
                "yes_ask_depth": 3,
                "no_ask_depth": 2,
            },
        ),
        PointInTimeEvidence(
            evidence_id=f"incumbent-{market_id}",
            source_family="incumbent-specialist",
            observed_at=NOW - timedelta(seconds=2),
            received_at=NOW,
            source_reference=f"fixture://incumbent/{market_id}",
            observed_at_verified=True,
            received_at_verified=True,
            payload={
                "kind": "incumbent_forecast",
                "market_id": market_id,
                "probability_yes": probability,
                "uncertainty": incumbent_uncertainty,
                "source_family": (
                    "mlb-structural" if sport else "crypto-coinbase-distribution"
                ),
                "source": "frozen-incumbent-fixture",
                "model_version": "incumbent-fixture-v1",
                "calibration_identity": "incumbent-fixture-calibration-v1",
                "features": {},
                "assumptions": ["frozen_inputs_are_complete"],
                "failure_conditions": ["unobserved_regime_change"],
            },
        ),
        PointInTimeEvidence(
            evidence_id=f"calibration-{market_id}",
            source_family="settled-calibration",
            observed_at=NOW - timedelta(minutes=1),
            received_at=NOW - timedelta(seconds=1),
            source_reference=f"fixture://calibration/{market_id}",
            observed_at_verified=True,
            received_at_verified=True,
            payload={
                "kind": "calibration_map",
                "verified": True,
                "offset": 0.0,
                "map_version": "fixture-calibration-v1",
            },
        ),
    )
    settlement = VerifiedSettlement(
        market_id=market_id,
        event_cluster_id=f"cluster-{market_id}",
        result_yes=True,
        market_closed_at=close,
        settled_at=close + timedelta(minutes=1),
        received_at=close + timedelta(minutes=2),
        source="verified-fixture-settlement",
        source_reference=f"fixture://settlement/{market_id}",
        verified=True,
    )
    issue = IssueRequest(
        market_id=market_id,
        market_type=market_type,
        vertical=vertical,
        clock_domain=clock,
        objective=objective,
        policy_version="phase3-policy-v1",
        decision_at=NOW,
        market_close_at=close,
        event_cluster_id=f"cluster-{market_id}",
        evidence=evidence,
        max_shadow_contracts=2,
    )
    return EpisodeRequest(
        issue=issue,
        settlement=settlement,
        held_out_cases=_held_out_cases(),
    )


@pytest.mark.parametrize("sport", [False, True])
def test_complete_episode_covers_all_twenty_steps_and_dissolves(sport: bool) -> None:
    artifact = run_complete_episode(_request(sport=sport), ledger=InMemoryEpisodeLedger())
    payload = artifact.to_dict()
    assert [item["number"] for item in payload["capability_steps"]] == list(range(1, 21))
    assert all(item["status"] == "COMPLETE" for item in payload["capability_steps"])
    assert payload["status"] == "DISSOLVED"
    assert payload["morphology"]["dissolved_after_issuance"] is True
    assert len(payload["morphology"]["activation_order"]) == 7
    assert len(payload["agent_grades"]) == 7
    assert len(payload["competing_futures"]) == 3
    assert payload["decision"]["incumbent_substituted"] is False
    assert payload["governance"]["execution_authority"] is False
    assert payload["governance"]["broker_contacted"] is False
    assert payload["shadow_execution"]["lane"] == "shadow"
    assert payload["shadow_execution"]["realized"] is False
    for history in payload["morphology"]["lifecycle"].values():
        assert history[-1]["current"] == "RETIRED"


def test_issue_and_later_completion_are_structurally_separate() -> None:
    request = _request()
    issued = issue_episode(request.issue)
    issued_payload = issued.to_dict()
    assert issued_payload["status"] == "ISSUED"
    assert "settlement" not in issued_payload
    assert "held_out_replay" not in issued_payload
    assert len(issued_payload["capability_steps"]) == 13

    complete = complete_issued_episode(
        issued,
        settlement=request.settlement,
        held_out_cases=request.held_out_cases,
        ledger=InMemoryEpisodeLedger(),
    )
    assert complete.episode_id == issued.episode_id
    assert complete.to_dict()["issuance_digest"] == issued.digest()
    assert len(complete.to_dict()["capability_steps"]) == 20


def test_phase4_world_state_version_is_frozen_and_propagated_to_every_agent() -> None:
    issued = issue_episode(_request().issue).to_dict()
    state_message = issued["frozen_world_state"]
    state_payload = state_message["payload"]
    world_state = state_payload["world_state"]
    state_version = state_payload["state_version"]
    assert world_state["snapshot_id"] == state_version
    assert world_state["frozen"] is True
    assert world_state["schema"]["scope"] == "crypto_horizon:fifteen_minute"
    assert world_state["completeness"] < 1.0
    assert any(
        item["status"] == "missing" and item["uncertainty"] == 1.0
        for item in world_state["values"]
    )
    assert {
        message["payload"]["world_state_version"]
        for message in issued["agent_messages"]
    } == {state_version}
    assert (
        issued["decision"]["message"]["payload"]["world_state_version"]
        == state_version
    )


def test_phase5_controls_are_structured_conservative_and_shadow_only() -> None:
    issued = issue_episode(_request().issue).to_dict()
    decision = issued["decision"]["message"]["payload"]
    review = decision["shadow_review"]
    metacognition = decision["metacognition"]
    metabolism = decision["metabolism"]

    assert {item["guard"] for item in review["findings"]} == {
        "authority",
        "confidence",
        "duplication",
        "leakage",
        "market_prior",
        "provenance",
        "regime",
        "resource",
    }
    assert review["authority_can_only_contract"] is True
    assert review["execution_authority"] is False
    assert review["promotion_authority"] == "HUMAN_ONLY"
    assert decision["family_weights"]["market-price"] >= 0.50
    assert sum(decision["family_weights"].values()) == pytest.approx(1.0)
    assert decision["structured_synthesis"]["market_prior_floor"] == 0.50

    assert metacognition["shadow_only"] is True
    assert metacognition["execution_authority"] is False
    assert metacognition["promotion_authority"] == "HUMAN_ONLY"
    assert metacognition["difficulty"]["calibration"]["state"] == (
        "UNCALIBRATED_SHADOW"
    )
    for recommendation in (
        "abstention",
        "resource_allocation",
        "stopping",
        "strategy",
    ):
        assert metacognition[recommendation]["applied"] is False

    marginal = metabolism["marginal_utility"]
    assert marginal["status"] == "UNRESOLVED_UNMEASURED_COST"
    assert marginal["marginal_utility"] is None
    assert marginal["automatic_resource_expansion"] is False


def test_episode_replay_is_byte_identical() -> None:
    request = _request()
    first = run_complete_episode(request, ledger=InMemoryEpisodeLedger())
    second = run_complete_episode(request, ledger=InMemoryEpisodeLedger())
    assert artifact_bytes(first) == artifact_bytes(second)
    verification = verify_deterministic_replay(request)
    assert verification.byte_identical is True
    assert verification.first_size_bytes == verification.second_size_bytes


def test_episode_request_schema_round_trips_without_semantic_drift() -> None:
    request = _request(sport=True)
    restored = EpisodeRequest.from_dict(request.semantic_dict())
    assert restored == request
    assert restored.episode_id() == request.episode_id()


def test_no_edge_path_issues_typed_abstention_and_never_simulates_order() -> None:
    artifact = run_complete_episode(
        _request(incumbent_probability=0.50),
        ledger=InMemoryEpisodeLedger(),
    )
    payload = artifact.to_dict()
    assert payload["decision"]["decision_kind"] == "ABSTAIN"
    assert payload["decision"]["message"]["message_type"] == "ABSTENTION"
    assert "edge_inside_no_edge_band" in payload["decision"]["message"]["payload"]["abstain_reasons"]
    assert payload["shadow_execution"]["status"] == "NO_ORDER_ABSTAINED"
    assert payload["shadow_execution"]["order_submitted"] is False


def test_adversarial_hard_limit_propagates_to_shadow_abstention() -> None:
    artifact = run_complete_episode(
        _request(incumbent_probability=1.0),
        ledger=InMemoryEpisodeLedger(),
    )
    payload = artifact.to_dict()
    adversary = next(
        item
        for item in payload["agent_messages"]
        if item["payload"].get("organism_role") == "adversary"
    )
    assert adversary["message_type"] == "VETO"
    assert payload["decision"]["decision_kind"] == "ABSTAIN"
    assert payload["shadow_execution"]["order_submitted"] is False


def test_future_received_evidence_fails_before_forecasting() -> None:
    with pytest.raises(EpisodeValidationError, match="future-received"):
        _request(future_receipt=True)


def test_episode_identity_is_frozen_before_settlement_and_replay_inputs() -> None:
    request = _request()
    changed_settlement = replace(
        request.settlement,
        result_yes=not request.settlement.result_yes,
    )
    changed_held_out = tuple(
        replace(case, result_yes=not case.result_yes)
        for case in request.held_out_cases
    )
    later_truth = replace(
        request,
        settlement=changed_settlement,
        held_out_cases=changed_held_out,
    )
    assert later_truth.episode_id() == request.episode_id()
    assert later_truth.semantic_dict() != request.semantic_dict()
    first = run_complete_episode(request, ledger=InMemoryEpisodeLedger()).to_dict()
    later = run_complete_episode(later_truth, ledger=InMemoryEpisodeLedger()).to_dict()
    assert first["decision"] == later["decision"]
    assert first["shadow_execution"] == later["shadow_execution"]
    assert first["settlement"] != later["settlement"]


def test_unverified_evidence_timestamp_cannot_enter_replay() -> None:
    with pytest.raises(EpisodeValidationError, match="unverified provider timestamp"):
        PointInTimeEvidence(
            evidence_id="bad-evidence",
            source_family="bad-source",
            observed_at=NOW,
            received_at=NOW,
            source_reference="fixture://bad",
            observed_at_verified=False,
            received_at_verified=True,
            payload={"kind": "market_quote"},
        )


def test_held_out_clusters_must_be_distinct_from_training_and_each_other() -> None:
    request = _request()
    duplicate = replace(
        request.held_out_cases[1],
        event_cluster_id=request.held_out_cases[0].event_cluster_id,
    )
    with pytest.raises(EpisodeValidationError, match="unique event clusters"):
        replace(
            request,
            held_out_cases=(request.held_out_cases[0], duplicate),
        )


def test_unverified_settlement_cannot_enter_complete_episode() -> None:
    with pytest.raises(EpisodeValidationError, match="unverified settlement"):
        VerifiedSettlement(
            market_id="KXBTC15M-TEST",
            event_cluster_id="cluster-1",
            result_yes=True,
            market_closed_at=NOW,
            settled_at=NOW,
            received_at=NOW,
            source="fixture",
            source_reference="fixture://settlement",
            verified=False,
        )


def test_jsonl_ledger_is_canonical_persistent_and_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "vnext" / "episodes.jsonl"
    ledger = JsonlEpisodeLedger(path)
    artifact = run_complete_episode(_request(), ledger=ledger)
    assert ledger.append(artifact) == artifact.episode_id
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
    assert ledger.get(artifact.episode_id).to_json() == artifact.to_json()
    assert ledger.records() == (artifact,)


def test_cli_persists_issue_then_attaches_later_truth(tmp_path: Path) -> None:
    request = _request()
    issue_input = tmp_path / "issue.json"
    issued_output = tmp_path / "issued.json"
    truth_input = tmp_path / "truth.json"
    ledger_path = tmp_path / "episodes.jsonl"
    issue_input.write_text(
        json.dumps(request.issue.semantic_dict()),
        encoding="utf-8",
    )
    truth_input.write_text(
        json.dumps(
            {
                "settlement": request.settlement.to_dict(),
                "held_out_cases": [item.to_dict() for item in request.held_out_cases],
            }
        ),
        encoding="utf-8",
    )
    script = Path(__file__).parents[1] / "scripts" / "run_vnext_phase3_episode.py"
    issued = subprocess.run(
        [
            sys.executable,
            str(script),
            "issue",
            "--input",
            str(issue_input),
            "--output",
            str(issued_output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(issued.stdout)["status"] == "ISSUED"
    assert "settlement" not in json.loads(issued_output.read_text(encoding="utf-8"))
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "complete",
            "--issued",
            str(issued_output),
            "--truth",
            str(truth_input),
            "--ledger",
            str(ledger_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout)["status"] == "DISSOLVED"
    assert len(ledger_path.read_text(encoding="utf-8").splitlines()) == 1


def test_artifact_parser_rejects_promotion_or_execution_boundary_tampering() -> None:
    artifact = run_complete_episode(_request(), ledger=InMemoryEpisodeLedger())
    unsafe = copy.deepcopy(artifact.to_dict())
    unsafe["promotion_candidate"]["eligible_for_promotion"] = True
    with pytest.raises(EpisodeValidationError, match="promotion boundary"):
        EpisodeArtifact(unsafe)

    unsafe = copy.deepcopy(artifact.to_dict())
    unsafe["shadow_execution"]["broker_contacted"] = True
    with pytest.raises(EpisodeValidationError, match="execution truth"):
        EpisodeArtifact(unsafe)

    issued = issue_episode(_request().issue)
    unsafe_issued = copy.deepcopy(issued.to_dict())
    unsafe_issued["settlement"] = {"result_yes": True}
    with pytest.raises(EpisodeValidationError, match="future truth"):
        IssuedEpisodeArtifact(unsafe_issued)

    unsafe_issued = copy.deepcopy(issued.to_dict())
    unsafe_issued["decision"]["candidate_probability"] = 0.99
    with pytest.raises(EpisodeValidationError, match="decision digest"):
        IssuedEpisodeArtifact(unsafe_issued)


def test_held_out_replay_is_cluster_purged_and_never_applied() -> None:
    artifact = run_complete_episode(_request(), ledger=InMemoryEpisodeLedger())
    payload = artifact.to_dict()
    replay = payload["held_out_replay"]
    candidate = payload["promotion_candidate"]
    assert replay["event_cluster_purged"] is True
    assert replay["held_out_case_count"] == 5
    assert replay["applied"] is False
    assert candidate["automatic_promotion"] is False
    assert candidate["promotion_authority"] == "HUMAN_ONLY"
    assert candidate["eligible_for_promotion"] is False
    assert candidate["applied"] is False


def test_organism_package_has_no_broker_credential_or_legacy_identity_imports() -> None:
    root = Path(__file__).parents[1] / "dummy" / "organisms"
    forbidden_roots = {
        "core.inherited_blunder",
        "kalshi.auth",
        "kalshi.client",
        "live_firewall.firewall",
        "autonomy.executor",
    }
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
        assert imports.isdisjoint(forbidden_roots), (path, imports & forbidden_roots)
        assert "inherited_blunder" not in path.read_text(encoding="utf-8")
