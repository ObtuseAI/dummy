"""Tests for dashboard V3 next-proof-candidate status endpoint."""

from __future__ import annotations

import json


from dashboard.backend.operator_control_routes import _load_v3_status


def test_v3_status_not_generated_yet(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "dashboard.backend.operator_control_routes.V3_CANDIDATE_PATH", tmp_path / "v3.json"
    )
    monkeypatch.setattr(
        "dashboard.backend.operator_control_routes.V3_REPORT_PATH", tmp_path / "v3_report.json"
    )
    status = _load_v3_status()
    assert status["status"] == "not_generated_yet"
    assert status["candidate_found"] is False
    assert status["submit_allowed_now"] is False
    assert status["requires_new_operator_proof_authority"] is True
    assert status["no_submit_button"] is True
    assert status["no_live_submit_auto_enable"] is True


def test_v3_status_candidate_found(tmp_path, monkeypatch):
    candidate_path = tmp_path / "v3.json"
    report_path = tmp_path / "v3_report.json"
    monkeypatch.setattr("dashboard.backend.operator_control_routes.V3_CANDIDATE_PATH", candidate_path)
    monkeypatch.setattr("dashboard.backend.operator_control_routes.V3_REPORT_PATH", report_path)

    candidate_path.write_text(
        json.dumps(
            {
                "validation_mode": "read_only_discovery",
                "discovery_mode": "broad",
                "candidate_found": True,
                "market_ticker": "KXACTIVE-S2026ABCD-1234",
                "contract_ticker": "KXACTIVE-S2026ABCD-1234",
                "market_status": "open",
                "contract_status": "open",
                "market_tradable": True,
                "contract_tradable": True,
                "price_validated": True,
                "price_source": "metadata",
                "price": 1,
                "read_only_metadata_contact": True,
                "get_request_count": 1,
                "write_request_count": 0,
                "blocked_write_request_count": 0,
                "response_schema_summary": "keys:cursor,markets",
                "candidate_selection_trace": ["live_eligible_candidate_found"],
                "exact_blockers": [],
                "submit_allowed_now": False,
                "requires_new_operator_proof_authority": True,
                "secrets_redacted": True,
            }
        ),
        encoding="utf-8",
    )
    report_path.write_text(
        json.dumps(
            {
                "verdict": "READ_ONLY_DISCOVERY_V3_CANDIDATE_FOUND",
                "candidate_found": True,
            }
        ),
        encoding="utf-8",
    )

    status = _load_v3_status()
    assert status["status"] == "READ_ONLY_DISCOVERY_V3_CANDIDATE_FOUND"
    assert status["candidate_found"] is True
    assert status["market_ticker"] == "KXACTIVE-S2026ABCD-1234"
    assert status["market_tradable"] is True
    assert status["price_validated"] is True
    assert status["price"] == 1
    assert status["get_request_count"] == 1
    assert status["write_request_count"] == 0
    assert status["exact_blockers"] == []
    assert status["submit_allowed_now"] is False
    assert status["requires_new_operator_proof_authority"] is True


def test_v3_status_blocked_candidate(tmp_path, monkeypatch):
    candidate_path = tmp_path / "v3.json"
    report_path = tmp_path / "v3_report.json"
    monkeypatch.setattr("dashboard.backend.operator_control_routes.V3_CANDIDATE_PATH", candidate_path)
    monkeypatch.setattr("dashboard.backend.operator_control_routes.V3_REPORT_PATH", report_path)

    candidate_path.write_text(
        json.dumps(
            {
                "validation_mode": "read_only_discovery",
                "discovery_mode": "broad",
                "candidate_found": False,
                "market_ticker": "KXBTC-26DEC25000-C",
                "contract_ticker": "KXBTC-26DEC25000-C",
                "market_status": "unknown",
                "contract_status": "unknown",
                "market_tradable": False,
                "contract_tradable": False,
                "price_validated": False,
                "price_source": "unknown",
                "price": 0,
                "read_only_metadata_contact": True,
                "get_request_count": 1,
                "write_request_count": 0,
                "blocked_write_request_count": 0,
                "response_schema_summary": "unknown_shape",
                "candidate_selection_trace": ["NO_MARKETS_RETURNED"],
                "exact_blockers": ["NO_MARKETS_RETURNED"],
                "submit_allowed_now": False,
                "requires_new_operator_proof_authority": True,
                "secrets_redacted": True,
            }
        ),
        encoding="utf-8",
    )
    report_path.write_text(
        json.dumps(
            {
                "verdict": "READ_ONLY_DISCOVERY_V3_NO_CANDIDATE",
                "exact_blockers": ["NO_MARKETS_RETURNED"],
            }
        ),
        encoding="utf-8",
    )

    status = _load_v3_status()
    assert status["status"] == "READ_ONLY_DISCOVERY_V3_NO_CANDIDATE"
    assert status["candidate_found"] is False
    assert status["exact_blockers"] == ["NO_MARKETS_RETURNED"]
    assert status["no_submit_button"] is True


def test_v3_status_no_secrets_in_output(tmp_path, monkeypatch):
    candidate_path = tmp_path / "v3.json"
    report_path = tmp_path / "v3_report.json"
    monkeypatch.setattr("dashboard.backend.operator_control_routes.V3_CANDIDATE_PATH", candidate_path)
    monkeypatch.setattr("dashboard.backend.operator_control_routes.V3_REPORT_PATH", report_path)

    candidate_path.write_text(
        json.dumps(
            {
                "candidate_found": True,
                "secrets_redacted": True,
                "api_key": "should_not_appear_in_real_usage",
            }
        ),
        encoding="utf-8",
    )
    report_path.write_text(json.dumps({"verdict": "PASS"}), encoding="utf-8")

    status = _load_v3_status()
    # Dashboard status must not expose raw credential-like fields.
    assert "api_key" not in status
    assert status["secrets_redacted"] is True
