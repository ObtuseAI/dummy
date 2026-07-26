from __future__ import annotations

import hashlib
from pathlib import Path

from core.caps_authority import CAPS_CONFIG_INTACT_STATES, evaluate_caps_authority
from predator_mesh.authority_contracts import CAPS_HASH, LIVE_SUBMIT_HASH
from predator_mesh.staged_gate_common import safe_base

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_protected_hashes_match_the_current_tracked_files() -> None:
    assert _sha256(ROOT / "configs" / "live_submit.json") == LIVE_SUBMIT_HASH
    assert _sha256(ROOT / "configs" / "caps.json") == CAPS_HASH


def test_caps_integrity_never_self_grants_execution_authority() -> None:
    status = evaluate_caps_authority()
    assert status.current_caps_sha256 == CAPS_HASH
    assert status.config_integrity_valid is True
    # Caps config must be INTACT. Whether an operator has registered is their
    # prerogative and moves this between the two intact states; pinning
    # REVIEW_REQUIRED asserted they had not exercised a sanctioned path, which
    # turned red the moment they did. CONFIG_INTEGRITY_BLOCKED still fails
    # here, so tamper detection is unchanged.
    assert status.state in CAPS_CONFIG_INTACT_STATES
    assert isinstance(status.authority_registration_valid, bool)
    assert status.legacy_authority_invalidated is True
    # The invariant that actually matters, true in either intact state.
    assert status.execution_authority is False


def test_stable_report_base_never_self_grants_authority() -> None:
    report = safe_base(
        "STABLE_CONTRACT_TEST",
        "protected hash and authority invariant",
        "PASS",
    )

    assert report["live_trading_enabled"] is False
    assert report["live_order_submitted"] is False
    assert report["broker_submit_call_made"] is False
    assert report["approval_file_write_attempted"] is False
