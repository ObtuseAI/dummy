from __future__ import annotations


def test_outcome_backed_signal_bloodline_credits_no_trade_signals() -> None:
    from predator_mesh.v17.bloodlines import OutcomeBackedSignalBloodline

    report = OutcomeBackedSignalBloodline().to_report()

    assert "helpful_no_trade_signal_credit" in report
    assert report["domain_separated"] is True
