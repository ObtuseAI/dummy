"""Tests for the aggression allocation manifest output."""

from __future__ import annotations

import pytest

from predator_mesh.aggression.models import AggressionAllocation, AggressionDecision


def test_manifest_contains_decision_and_size() -> None:
    allocation = AggressionAllocation(
        decision=AggressionDecision.ATTACK,
        size_pct=0.85,
        confidence=0.75,
        reasoning="strong edge",
        blocked_by=[],
        meta={"edge_candidate_id": "abc"},
    )
    manifest = allocation.to_manifest_entry()
    assert manifest["decision"] == "attack"
    assert manifest["size_pct"] == pytest.approx(0.85)
    assert manifest["confidence"] == pytest.approx(0.75)
    assert manifest["reasoning"] == "strong edge"
    assert manifest["blocked_by"] == []
    assert manifest["meta"]["edge_candidate_id"] == "abc"


def test_manifest_size_is_clamped() -> None:
    allocation = AggressionAllocation(size_pct=1.5, confidence=2.0)
    manifest = allocation.to_manifest_entry()
    assert manifest["size_pct"] == pytest.approx(1.0)
    assert manifest["confidence"] == pytest.approx(1.0)


def test_manifest_for_pass_decision() -> None:
    allocation = AggressionAllocation(
        decision=AggressionDecision.PASS,
        size_pct=0.0,
        confidence=0.3,
        reasoning="cap breach",
        blocked_by=["cap_breach"],
    )
    manifest = allocation.to_manifest_entry()
    assert manifest["decision"] == "pass"
    assert manifest["size_pct"] == pytest.approx(0.0)
    assert "cap_breach" in manifest["blocked_by"]


def test_manifest_has_proof_reference() -> None:
    allocation = AggressionAllocation()
    manifest = allocation.to_manifest_entry()
    assert isinstance(manifest["proof_reference"], str)
    assert manifest["proof_reference"].startswith("agg_")
