"""The ratchet must be CHARGED by the real demotion path, not just exist.

This repo has been bitten before by machinery that was written, documented, and
never wired (the claim compiler). A ratchet nobody charges is a ratchet that
does nothing, and it would silently leave a low promotion bar with no
compensating penalty -- the exact combination Wave-86 must not ship.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_dummy_readiness_report.py"
SCOPE = "crypto_technical_foundry|sol|15m_direction|15m"


@pytest.fixture()
def runner(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("readiness_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["readiness_under_test"] = module
    spec.loader.exec_module(module)
    # Keep every write inside tmp_path.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "runtime" / "autonomy").mkdir(parents=True, exist_ok=True)
    return module


def _ratchet_count(scope=SCOPE):
    from autonomy.promotion_ratchet import load_ratchet, requirements_for

    return requirements_for(
        load_ratchet(), scope, base_clusters=3,
    )["prior_demotions"]


def test_new_demotion_charges_the_ratchet(runner, tmp_path):
    path = tmp_path / "runtime" / "autonomy" / "auto_demotions.json"
    fresh = {"demotions": [{"scope": SCOPE, "detected_at": "t0"}]}

    assert _ratchet_count() == 0
    runner._merge_demotions(path, fresh, "2026-07-24T00:00:00+00:00")
    assert _ratchet_count() == 1, "a demotion must raise the next promotion's price"


def test_repeated_demotion_of_the_same_scope_is_charged_once(runner, tmp_path):
    """The daily report re-emits standing demotions; only NEW ones count."""
    path = tmp_path / "runtime" / "autonomy" / "auto_demotions.json"
    fresh = {"demotions": [{"scope": SCOPE, "detected_at": "t0"}]}

    merged = runner._merge_demotions(path, fresh, "2026-07-24T00:00:00+00:00")
    path.write_text(__import__("json").dumps(merged), encoding="utf-8")
    assert _ratchet_count() == 1

    # Same scope, next nightly run: already recorded, must not double-charge.
    runner._merge_demotions(path, fresh, "2026-07-25T00:00:00+00:00")
    assert _ratchet_count() == 1


def test_no_demotions_leaves_the_ratchet_untouched(runner, tmp_path):
    path = tmp_path / "runtime" / "autonomy" / "auto_demotions.json"
    merged = runner._merge_demotions(
        path, {"demotions": []}, "2026-07-24T00:00:00+00:00",
    )
    assert merged["ratchet_charged"] == 0
    assert _ratchet_count() == 0
