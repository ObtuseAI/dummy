from __future__ import annotations


def test_timeout_guards_still_intact_v17() -> None:
    from predator_mesh.v17.observer import SettlementStatusProbe

    probe = SettlementStatusProbe()
    assert probe.max_request_timeout_s <= 10
    assert probe.total_timeout_s <= 45
