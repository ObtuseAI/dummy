"""Forward-candidate registration is idempotent, bounded, and authority-free."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.register_forward_candidates import (
    CANDIDATES,
    build_registrations,
    candidate_fingerprint,
)
from autonomy.auto_promotion_runner import load_forward_registrations


ROOT = Path(__file__).resolve().parents[1]


def test_candidates_are_the_audited_edge_scopes():
    scopes = [scope for scope, _module in CANDIDATES]
    assert scopes == [
        "crypto_equities_flow|sol|ladder|daily+",
        "crypto_macro_regime|sol|ladder|daily+",
        # Current market_debias emission shape: market_type is stamped as
        # "<type>@<horizon>", so the stale "market_debias|mlb|na|pre" literal
        # could never match a live emission's grading scope.
        "market_debias|mlb|prop@long|pre",
        "market_debias|mlb|prop@short|pre",
        "market_debias|mlb|spread@long|pre",
    ]
    for scope, module in CANDIDATES:
        assert len(scope.split("|")) == 4
        assert (ROOT / module).is_file()


def test_market_debias_candidates_come_from_the_signal_module():
    """One source of truth: the signal's own eligibility gate.

    A literal repeated here is exactly how the registered scope went stale when
    the emission's market_type stamp changed.
    """
    from autonomy.signals.market_debias import PROMOTION_ELIGIBLE_SCOPES

    registered = {
        scope
        for scope, module in CANDIDATES
        if module == "autonomy/signals/market_debias.py"
    }
    assert registered == set(PROMOTION_ELIGIBLE_SCOPES)


def test_live_registrations_cover_every_eligible_market_debias_scope():
    """Registration is a precondition: an eligible scope must be registered."""
    from autonomy.signals.market_debias import PROMOTION_ELIGIBLE_SCOPES

    path = ROOT / "runtime" / "autonomy" / "promotion_forward_registrations.json"
    if not path.exists():  # fresh checkout with no runtime state
        return
    loaded = load_forward_registrations(path)
    assert set(PROMOTION_ELIGIBLE_SCOPES) <= set(loaded)


def test_fingerprint_binds_scope_and_implementation_bytes(tmp_path):
    module = tmp_path / "impl.py"
    module.write_text("A = 1\n", encoding="utf-8")
    first = candidate_fingerprint("s|a|m|h", module)
    assert len(first) == 64 and first == first.lower()
    assert candidate_fingerprint("other|a|m|h", module) != first
    module.write_text("A = 2\n", encoding="utf-8")
    assert candidate_fingerprint("s|a|m|h", module) != first


def test_build_is_idempotent_and_never_redates():
    document, added = build_registrations({})
    assert len(added) == len(CANDIDATES)
    again, added_again = build_registrations(document)
    assert added_again == []
    assert again["registrations"] == document["registrations"]


def test_written_document_passes_the_runner_loader(tmp_path):
    document, _added = build_registrations({})
    path = tmp_path / "promotion_forward_registrations.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    loaded = load_forward_registrations(path)
    assert set(loaded) == {scope for scope, _module in CANDIDATES}
    for scope, entry in loaded.items():
        assert entry["candidate_fingerprint"]
        assert entry["registered_at"]


def test_registration_document_claims_no_authority():
    document, _added = build_registrations({})
    for entry in document["registrations"]:
        assert entry["authority"] == (
            "none_registration_is_a_precondition_not_a_promotion"
        )
