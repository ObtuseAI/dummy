from __future__ import annotations

from predator_mesh import operator_status


def _artifacts(values):
    return lambda name: values.get(name, {})


def test_activation_snapshot_is_read_only_and_fail_closed(monkeypatch):
    monkeypatch.setattr(operator_status.sgc, "load_artifact", _artifacts({}))

    snapshot = operator_status.build_activation_snapshot()

    assert snapshot["safe_mode"] == "READ_ONLY_FAIL_CLOSED"
    assert snapshot["ui_submit_enabled"] is False
    assert snapshot["ui_config_write_enabled"] is False
    assert snapshot["broker_contacted"] is False
    assert snapshot["live_proof_status"].startswith("PARTIAL_")


def test_authority_resolver_defaults_to_dry_locked(monkeypatch):
    monkeypatch.setattr(operator_status.sgc, "load_artifact", _artifacts({}))
    monkeypatch.setattr(
        operator_status.sgc,
        "baseline_status",
        lambda *_args: "PARTIAL_V207_BASELINE_ABSENT",
    )

    status = operator_status.resolve_authority()

    assert status == {
        "authority_state": "DRY_LOCKED",
        "armable": False,
        "controller_status": "PARTIAL_AUTHORITY_RESOLVER_NOT_ARMABLE",
        "blockers": [
            "EXACT_APPROVAL_ABSENT",
            "CONFIG_CAPS_QUORUM_ABSENT",
            "FIREWALL_ADAPTER_ABSENT",
        ],
        "execution_authority": False,
    }


def test_authority_resolver_fixture_armable_never_grants_execution(monkeypatch):
    monkeypatch.setattr(
        operator_status.sgc, "baseline_status", lambda *_args: "PASS_V207_BASELINE"
    )

    status = operator_status.resolve_authority(
        approval_ok_override=True,
        config_ok_override=True,
        firewall_ok_override=True,
        proof_already_locked_override=False,
    )

    assert status["authority_state"] == "LIVE_PROOF_ARMABLE"
    assert status["armable"] is True
    assert status["execution_authority"] is False


def test_completion_scoreboard_reads_evidence_without_authority(monkeypatch):
    monkeypatch.setattr(
        operator_status.sgc,
        "load_artifact",
        _artifacts(
            {
                "final_report_v209.json": {
                    "live_proof_runner_controller_status": (
                        "PASS_LIVE_PROOF_RUNNER_SUBMITTED_AUTOLOCKED"
                    )
                },
                "final_report_v210.json": {
                    "reconcile_runner_controller_status": (
                        "PASS_RECONCILE_RUNNER_STATE_CLASSIFIED_AUTOLOCKED"
                    )
                },
                "final_report_v211.json": {
                    "forensic_runner_controller_status": (
                        "PASS_FORENSIC_RUNNER_REVIEWED_LOCKED"
                    )
                },
                "final_report_v205.json": {"canonical_blocker_list": ["EDGE"]},
            }
        ),
    )

    scoreboard = operator_status.build_completion_scoreboard()

    assert scoreboard["proof_status_count"] == 3
    assert scoreboard["remaining_blocker_count"] == 1
    assert scoreboard["execution_authority"] is False
