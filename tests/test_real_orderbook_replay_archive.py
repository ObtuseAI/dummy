from __future__ import annotations

import json

from predator_mesh.v13.replay_v2 import RealOrderbookReplayArchive, RealOrderbookReplayStore
from tests.v13_test_helpers import real_snapshot_result


def test_real_orderbook_replay_archive_excludes_account_sensitive_fields() -> None:
    store = RealOrderbookReplayStore()
    store.add_snapshot(real_snapshot_result())

    archive = RealOrderbookReplayArchive(store).to_report()
    text = json.dumps(archive).lower()

    assert archive["sanitized"] is True
    assert "balance" not in text
    assert "position" not in text
    assert archive["verdict"] == "PASS"
