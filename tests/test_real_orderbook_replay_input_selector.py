from __future__ import annotations

from tests.v16_test_helpers import real_snapshot


def test_replay_input_selector_prefers_real_snapshot() -> None:
    from predator_mesh.v16.replay_truth import RealOrderbookReplayInputSelector

    selection = RealOrderbookReplayInputSelector(snapshot_result=real_snapshot()).select()

    assert selection.input_mode == "REAL_SNAPSHOT_REPLAY"
    assert selection.snapshot_source == "config_bound_real_orderbook_snapshot"


def test_replay_input_selector_keeps_nonempty_degraded_real_snapshot() -> None:
    from predator_mesh.v16.replay_truth import RealOrderbookReplayInputSelector
    from tests.v16_test_helpers import OneSidedRealKalshiReadOnlyClient, real_snapshot

    selection = RealOrderbookReplayInputSelector(snapshot_result=real_snapshot(OneSidedRealKalshiReadOnlyClient())).select()

    assert selection.input_mode == "REAL_SNAPSHOT_REPLAY_WITH_WARNINGS"
    assert selection.snapshot_source == "config_bound_real_orderbook_snapshot"
