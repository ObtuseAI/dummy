from __future__ import annotations

import json
from pathlib import Path

import pytest

from dummy.constitution import (
    CONSTITUTIONAL_INVARIANTS,
    PROTECTED_SURFACES,
    RESEARCH_AUTHORITY_CEILING,
    Authority,
    AuthorityViolation,
    assert_authority_at_most,
    can_delegate,
    evaluate_mutation_proposal,
    protected_manifest_digest,
)
from dummy.constitution.mutation_protection import protected_manifest_dict


def test_authority_lattice_is_strictly_monotonic() -> None:
    authorities = list(Authority)
    assert authorities == sorted(authorities)
    assert len({item.value for item in authorities}) == len(authorities)

    for grant in authorities:
        for delegated in authorities:
            assert can_delegate(grant, delegated) is (delegated <= grant)
            assert grant.allows(delegated) is (delegated <= grant)


def test_research_authority_ceiling_fails_closed() -> None:
    assert RESEARCH_AUTHORITY_CEILING is Authority.SIMULATE
    assert_authority_at_most(
        Authority.SIMULATE,
        RESEARCH_AUTHORITY_CEILING,
        component="shadow-agent",
    )
    with pytest.raises(AuthorityViolation, match="RECOMMEND.*SIMULATE"):
        assert_authority_at_most(
            Authority.RECOMMEND,
            RESEARCH_AUTHORITY_CEILING,
            component="shadow-agent",
        )


def test_constitutional_registry_is_complete_and_unique() -> None:
    codes = [item.code for item in CONSTITUTIONAL_INVARIANTS]
    assert len(codes) == 14
    assert len(set(codes)) == len(codes)
    assert all(item.statement.strip() for item in CONSTITUTIONAL_INVARIANTS)
    assert all(item.protected_evidence.strip() for item in CONSTITUTIONAL_INVARIANTS)


def test_every_protected_surface_exists_in_repository() -> None:
    missing = [surface.path for surface in PROTECTED_SURFACES if not Path(surface.path).exists()]
    assert missing == []


def test_protected_manifest_digest_is_stable_sha256() -> None:
    first = protected_manifest_digest()
    second = protected_manifest_digest()
    assert first == second
    assert len(first) == 64
    int(first, 16)


def test_persisted_protected_manifest_matches_code() -> None:
    persisted = json.loads(
        Path("docs/VNEXT_PROTECTED_SURFACES.json").read_text(encoding="utf-8")
    )
    assert persisted == protected_manifest_dict()


@pytest.mark.parametrize(
    "path",
    [
        "dummy/constitution/authority.py",
        "autonomy/ledger.py",
        "execution/adapter.py",
        "configs/live_submit.json",
        "kalshi/client.py",
    ],
)
def test_automatic_mutation_rejects_protected_surfaces(path: str) -> None:
    decision = evaluate_mutation_proposal(
        [path],
        proposer_authority=Authority.RECOMMEND,
    )
    assert decision.allowed is False
    assert decision.blocked_paths == (path,)
    assert any(reason.startswith("protected:") for reason in decision.reasons)


@pytest.mark.parametrize(
    "path",
    ["README.md", "dummy/unknown/idea.py", "../configs/caps.json", "/tmp/escape.py"],
)
def test_automatic_mutation_rejects_unknown_or_unsafe_roots(path: str) -> None:
    if path.startswith(("..", "/")):
        with pytest.raises(ValueError, match="unsafe repository path"):
            evaluate_mutation_proposal([path], proposer_authority=Authority.RECOMMEND)
        return

    decision = evaluate_mutation_proposal(
        [path],
        proposer_authority=Authority.RECOMMEND,
    )
    assert decision.allowed is False
    assert decision.blocked_paths == (path,)
    assert decision.reasons == (f"outside_evolvable_roots:{path}",)


def test_automatic_mutation_allows_only_declared_research_surface() -> None:
    decision = evaluate_mutation_proposal(
        ["dummy/agents/challenger.py", "dummy/forecasting/btc.py"],
        proposer_authority=Authority.RECOMMEND,
    )
    assert decision.allowed is True
    assert decision.blocked_paths == ()
    assert decision.reasons == ()

    elevated = evaluate_mutation_proposal(
        ["dummy/agents/challenger.py"],
        proposer_authority=Authority.PAPER_ALLOCATE,
    )
    assert elevated.allowed is False
    assert elevated.reasons == ("mutation_proposer_exceeds_recommend_authority",)


def test_empty_mutation_proposal_fails_closed() -> None:
    decision = evaluate_mutation_proposal([], proposer_authority=Authority.RECOMMEND)
    assert decision.allowed is False
    assert decision.reasons == ("empty_mutation_proposal",)
