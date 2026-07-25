"""The out-of-band weight recalibration must report what actually happened.

Observed live 2026-07-25: the run ended
``RECAL_ERROR OperationalError: database is locked``, ``DummyWeightsRecal``
reported ``LastTaskResult: 0``, and ``last_recalibration.json`` stayed 13 hours
old. Weights had in fact been written -- ``run_backtest(bootstrap_weights=True)``
lands them in the ledger, and the OOS gate artifact recorded ``adopted: true``
minutes earlier -- but the failure of a *later*, separate artifact (the
market-debias curve) discarded the record that the refresh had completed. So the
watchdog alarmed on weights that were current, the next run redid the whole
275-second pass, and nothing in the exit code said a thing.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_script_module():
    script_path = REPO_ROOT / "scripts" / "run_dummy_weights_recal.py"
    spec = importlib.util.spec_from_file_location(
        "run_dummy_weights_recal_under_test", script_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def recal(tmp_path, monkeypatch):
    """The script with its artifact paths redirected into tmp_path."""
    module = _load_script_module()
    runtime = tmp_path / "runtime" / "autonomy"
    runtime.mkdir(parents=True)
    monkeypatch.setattr(module, "RUNTIME", runtime)
    monkeypatch.setattr(module, "STAMP", runtime / "last_recalibration.json")
    monkeypatch.setattr(sys, "argv", ["run_dummy_weights_recal.py"])
    return module


def _install_backtest(module, monkeypatch, *, report=None, raises=None):
    """Stub the whole recal dependency graph; return call counters."""
    calls = {"backtest": 0, "curve": 0, "closed": 0}

    def fake_run_backtest(ledger, **kwargs):
        calls["backtest"] += 1
        if raises is not None:
            raise raises
        return report

    class FakeLedger:
        def close(self):
            calls["closed"] += 1

    fake_backtest_mod = SimpleNamespace(run_backtest=fake_run_backtest)
    fake_ledger_mod = SimpleNamespace(AutonomyLedger=lambda *a, **k: FakeLedger())

    def fake_write_curve(curve):
        calls["curve"] += 1
        if isinstance(curve, Exception):
            raise curve

    fake_debias = SimpleNamespace(
        fit_curve=lambda samples: samples,
        ledger_samples=lambda ledger: {},
        write_curve=fake_write_curve,
    )
    monkeypatch.setitem(sys.modules, "autonomy.backtest", fake_backtest_mod)
    monkeypatch.setitem(sys.modules, "autonomy.ledger", fake_ledger_mod)
    monkeypatch.setitem(sys.modules, "autonomy.signals.market_debias", fake_debias)
    return calls


_WROTE = {
    "settled_markets": 350_696,
    "derived_weights": {"crypto_patience_confirm": 1.635},
    "sources_by_scope": {"crypto_patience_confirm|sol|15m_direction|15m": {}},
    "weights_written": True,
    "weights_rejected_reasons": [],
}


def test_completed_refresh_is_stamped(recal, monkeypatch):
    calls = _install_backtest(recal, monkeypatch, report=_WROTE)

    assert recal.main() == 0
    assert calls["backtest"] == 1
    stamp = json.loads(recal.STAMP.read_text(encoding="utf-8"))
    assert stamp["weights_written"] is True
    assert stamp["settled_markets"] == 350_696
    assert stamp["out_of_band"] is True


def test_debias_curve_failure_does_not_discard_the_refresh_record(recal, monkeypatch):
    """The live failure. A lock on the curve must not erase the stamp."""
    calls = _install_backtest(recal, monkeypatch, report=_WROTE)
    monkeypatch.setitem(
        sys.modules,
        "autonomy.signals.market_debias",
        SimpleNamespace(
            fit_curve=lambda samples: samples,
            ledger_samples=lambda ledger: {},
            write_curve=lambda curve: (_ for _ in ()).throw(
                RuntimeError("database is locked")
            ),
        ),
    )

    exit_code = recal.main()

    assert recal.STAMP.exists(), "a completed weight write must stay recorded"
    stamp = json.loads(recal.STAMP.read_text(encoding="utf-8"))
    assert stamp["weights_written"] is True
    assert stamp["debias_curve_error"] == "RuntimeError"
    # The refresh succeeded; the side artifact did not. Reported, not fatal.
    assert exit_code == 0
    assert calls["closed"] == 1


def test_backtest_failure_reports_nonzero_and_leaves_the_stamp_alone(recal, monkeypatch):
    """A failed recalibration must not read as a successful task."""
    previous = {"at": "2026-07-24T19:00:01+00:00", "weights_written": True}
    recal.STAMP.write_text(json.dumps(previous), encoding="utf-8")
    _install_backtest(
        recal, monkeypatch, raises=RuntimeError("database is locked")
    )

    exit_code = recal.main()

    assert exit_code != 0, "a scheduled run that failed must say so in its exit code"
    assert json.loads(recal.STAMP.read_text(encoding="utf-8")) == previous


def test_rejected_weight_vector_does_not_advance_the_stamp(recal, monkeypatch):
    """Fail-closed: a rejected vector leaves the ledger's old weights in place.

    Advancing ``at`` would make ``_due()`` skip for six hours on weights that
    were never written -- the exact reverse of the bug above.
    """
    previous = {"at": "2026-07-24T19:00:01+00:00", "weights_written": True}
    recal.STAMP.write_text(json.dumps(previous), encoding="utf-8")
    _install_backtest(
        recal,
        monkeypatch,
        report={
            **_WROTE,
            "weights_written": False,
            "weights_rejected_reasons": ["floor_breach"],
        },
    )

    exit_code = recal.main()

    assert exit_code != 0
    assert json.loads(recal.STAMP.read_text(encoding="utf-8")) == previous


def test_fresh_weights_still_skip_without_touching_the_ledger(recal, monkeypatch):
    recal.STAMP.write_text(
        json.dumps({"at": datetime.now(timezone.utc).isoformat()}), encoding="utf-8"
    )
    calls = _install_backtest(recal, monkeypatch, report=_WROTE)

    assert recal.main() == 0
    assert calls["backtest"] == 0, "a fresh stamp must not open the 12GB ledger"


def test_stale_stamp_is_due(recal):
    old = datetime.now(timezone.utc) - timedelta(hours=7)
    recal.STAMP.write_text(json.dumps({"at": old.isoformat()}), encoding="utf-8")
    assert recal._due(datetime.now(timezone.utc)) is True
