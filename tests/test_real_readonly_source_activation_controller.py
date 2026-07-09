from __future__ import annotations

from v19_test_helpers import ALLOWED_MODES, DOMAINS, assert_pass_or_partial


def test_real_readonly_source_activation_controller_classifies_all_domains() -> None:
    from predator_mesh.v19.source_activation import RealReadOnlySourceActivationController

    report = RealReadOnlySourceActivationController().to_report()
    assert_pass_or_partial(report)
    assert set(report["domains"]) == DOMAINS
    assert set(report["activation_modes_by_domain"].values()) <= ALLOWED_MODES
    assert report["live_execution_enabled"] is False
