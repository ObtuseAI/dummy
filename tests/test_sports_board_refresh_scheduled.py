from __future__ import annotations

import inspect
from pathlib import Path

from autonomy import sports_board_refresh as refresh


def test_scheduled_refresh_defaults_to_provider_safe_concurrency() -> None:
    assert refresh.DEFAULT_MAX_WORKERS == 2
    signature = inspect.signature(refresh.refresh_sports_display_board)
    assert signature.parameters["max_workers"].default == 2


def test_installer_defines_bounded_independent_ignore_new_task() -> None:
    root = Path(__file__).resolve().parent.parent
    installer = (
        root / "scripts" / "install_sports_board_refresh_task.ps1"
    ).read_text(encoding="utf-8")
    runner = (root / "scripts" / "run_sports_board_refresh.py").read_text(
        encoding="utf-8"
    )
    monitor = (
        root / "scripts" / "run_dummy_mispricing_monitor.py"
    ).read_text(encoding="utf-8")

    assert '"DummySportsBoardRefresh"' in installer
    assert "[int]$StartDelayMinutes = 2" in installer
    assert "run_sports_board_refresh.py" in installer
    assert "-MultipleInstances IgnoreNew" in installer
    assert "ExecutionTimeLimit" in installer
    assert "run_dummy_mispricing_monitor.py" not in installer
    assert "build_brain" not in runner
    assert "autonomy.session" not in runner
    assert "sqlite3" not in runner
    assert "ledger.db" not in runner
    assert "run_scheduled_refresh" in runner
    assert "output_path=MODEL_SEED_PATH" in monitor
    assert "artifact_source=MODEL_SEED_ARTIFACT_SOURCE" in monitor
    assert "DISPLAY_BOARD_PATH" not in monitor


def test_os_held_refresh_lock_releases_without_deleting_lock_file(
    tmp_path: Path,
) -> None:
    lock_path = tmp_path / "sports_board_refresh.lock"

    with refresh._refresh_lock(lock_path) as acquired:
        assert acquired is True
        with refresh._refresh_lock(lock_path) as overlapping:
            assert overlapping is False

    # The harmless file may persist, but the kernel lock cannot remain sticky
    # after its owner closes or crashes.
    assert lock_path.exists()
    with refresh._refresh_lock(lock_path) as reacquired:
        assert reacquired is True
