"""Wave-28: the fast /api/status snapshot must carry vnext_shadow and
use_sidecar so their dashboard cards populate even while the heavy
/api/autonomy report is 503-ing (which it does under a busy ledger)."""
from __future__ import annotations

import json

from autonomy.dashboard import assemble_status_snapshot


def test_fast_snapshot_carries_vnext_and_use_cards(tmp_path):
    (tmp_path / "vnext_shadow_status.json").write_text(
        json.dumps({"issued": 8, "pending": 24, "completed": 0,
                    "episodes_on_ledger": 3, "errors": [],
                    "at": "2026-07-18T21:37:49+00:00"}),
        encoding="utf-8")
    (tmp_path / "use_predictions.json").write_text(
        json.dumps({"rows": [{"provenance": "use_sim_mlb"}]}), encoding="utf-8")

    snap = assemble_status_snapshot(runtime_dir=tmp_path)

    assert snap["ledger_touched"] is False  # still never touches the ledger
    assert snap["vnext_shadow"]["issued"] == 8
    assert snap["vnext_shadow"]["episodes_on_ledger"] == 3
    assert "use_sidecar" in snap and isinstance(snap["use_sidecar"], dict)


def test_fast_snapshot_defaults_when_files_absent(tmp_path):
    snap = assemble_status_snapshot(runtime_dir=tmp_path)
    assert snap["vnext_shadow"] == {}
    assert isinstance(snap["use_sidecar"], dict)
