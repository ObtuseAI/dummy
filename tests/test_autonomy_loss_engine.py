"""Loss-deconstruction evolution engine (WS-B): planted loss is localized to
the right cluster-level bucket, noise yields no confident claim, LLM
narration is fail-closed commentary only, family size is disclosed, the
tuner's priority read reorders/annotates without ever changing a walk-forward
verdict, and -- the one non-negotiable property -- no source file or
promotions.json is ever mutated by a full engine run."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import random
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from autonomy.loss_engine import (
    _categorical_buckets,
    _feature_buckets,
    build_loss_attribution,
    loss_priority,
    narrate_losses,
)
from autonomy.sports.nba_model import MODEL_VERSION as NBA_MODEL_VERSION
from autonomy.sports.nba_model import total_over_probability
from autonomy.strategy_miner import MinedRow
from autonomy.taxonomy import grading_scope
from autonomy.tuner import tuning_report

REPO_ROOT = Path(__file__).resolve().parent.parent
START = datetime(2026, 1, 1, tzinfo=timezone.utc)


# --------------------------------------------------------------------- fixtures


def _row(
    index: int, *, setup_score: float, probability_yes: float, market_probability: float,
    result_yes: bool, source: str = "nba_game_total", market_type: str = "total",
) -> MinedRow:
    ticker = f"KXNBATOTAL-26JAN{index:04d}LALBOS-200"
    features = {"setup_score": setup_score, "market_type": market_type, "sport": "nba"}
    when = (START + timedelta(hours=index)).isoformat()
    return MinedRow(
        source=source, ticker=ticker, event_cluster=f"CLUSTER-{index}", created_at=when,
        probability_yes=probability_yes, market_probability=market_probability,
        result_yes=result_yes, features=features,
        scope=grading_scope(source, ticker, features),
    )


def _planted_rows() -> list[MinedRow]:
    """30 clusters, one grading scope (nba|total|pre). The bottom tercile of
    ``setup_score`` (values 0-10, 11 rows after the tercile-cut boundary) is
    consistently and badly miscalibrated (probability_yes=0.9 when the
    market says 0.5 and the outcome is NO -- edge = 0.25 - 0.81 = -0.56 every
    time); the rest of the scope (values 11-29) prices exactly at the market
    (probability_yes == market_probability == 0.5 -> edge == 0.0 exactly,
    regardless of outcome). The scope-level mean is therefore negative
    (bleeding), and the low setup_score tercile is unambiguously the worst,
    cluster-level bucket."""
    rows: list[MinedRow] = []
    for i in range(10):
        rows.append(_row(
            i, setup_score=float(i), probability_yes=0.9, market_probability=0.5,
            result_yes=False,
        ))
    for i in range(10, 30):
        rows.append(_row(
            i, setup_score=float(i), probability_yes=0.5, market_probability=0.5,
            result_yes=(i % 2 == 0),
        ))
    return rows


def _noise_rows(seed: int = 7, n: int = 40) -> list[MinedRow]:
    """Every row prices exactly at the market (edge == 0.0 exactly) -- there
    is no real relationship between setup_score and the outcome beyond what
    the market already captures, so no scope can honestly bleed."""
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        rows.append(_row(
            i, setup_score=float(i % 5), probability_yes=0.5, market_probability=0.5,
            result_yes=rng.random() < 0.5,
        ))
    return rows


# --------------------------------------------------------------- B.1/B.2 attribution


def test_planted_loss_names_bleeding_bucket_cluster_level_with_ci():
    rows = _planted_rows()
    attribution = build_loss_attribution(rows, now_iso="2026-07-13T00:00:00+00:00")

    scope_entry = next(
        s for s in attribution["scopes"] if s["scope"] == "nba|nba|total|pre"
    )
    assert scope_entry["verdict"] == "bleeding"
    assert scope_entry["cluster_edge"] < 0.0
    assert scope_entry["n_clusters"] == 30

    labels = [bucket["bucket"] for bucket in scope_entry["worst_buckets"]]
    assert "setup_score:low" in labels
    worst = scope_entry["worst_buckets"][0]
    assert worst["bucket"] == "setup_score:low"
    assert worst["edge"] < 0.0
    assert worst["n_clusters"] >= 10
    # cluster-level CI present (not a per-row point estimate)
    assert worst["ci95"][0] is not None
    assert worst["ci95"][1] is not None
    assert worst["ci95"][0] <= worst["edge"] <= worst["ci95"][1]


def test_noise_rows_yield_no_bleeding_scope():
    rows = _noise_rows()
    attribution = build_loss_attribution(rows, now_iso="2026-07-13T00:00:00+00:00")
    scope_entry = next(
        s for s in attribution["scopes"] if s["scope"] == "nba|nba|total|pre"
    )
    # Every row edge is exactly 0.0 -> not < 0 -> never classified "bleeding".
    assert scope_entry["verdict"] in ("not_bleeding", "insufficient_data")
    assert scope_entry["worst_buckets"] == []
    assert all(s["verdict"] != "bleeding" for s in attribution["scopes"])


def test_family_size_disclosure_present_and_accurate():
    rows = _planted_rows()
    attribution = build_loss_attribution(rows, now_iso="2026-07-13T00:00:00+00:00")
    assert attribution["family_size"]["scopes_evaluated"] == 1

    expected_candidates = len(_feature_buckets(rows)) + len(_categorical_buckets(rows))
    # setup_score is the only NUMERIC_FEATURES entry with data here -> 3
    # tercile bands; market_type is constant ("total") -> 1; regime axis is
    # constant ("pre") -> 1. 5 total candidate buckets evaluated.
    assert expected_candidates == 5
    assert attribution["family_size"]["buckets_evaluated"] == expected_candidates


# --------------------------------------------------------------------- B.4 narration


def test_narration_absent_when_no_bleeding_scope():
    rows = _noise_rows()
    attribution = build_loss_attribution(rows, now_iso="2026-07-13T00:00:00+00:00")
    assert attribution["narration"] == {}

    class _Router:
        async def call(self, *args, **kwargs):  # pragma: no cover - must not be reached
            raise AssertionError("router must not be called when nothing is bleeding")

    assert narrate_losses(attribution, _Router()) == {}


def test_llm_down_narration_empty_deterministic_artifact_intact():
    rows = _planted_rows()
    attribution = build_loss_attribution(rows, now_iso="2026-07-13T00:00:00+00:00")
    assert attribution["narration"] == {}  # build never fills it itself

    class _RaisingRouter:
        async def call(self, *args, **kwargs):
            raise RuntimeError("router down")

    assert narrate_losses(attribution, _RaisingRouter()) == {}
    assert narrate_losses(attribution, None) == {}  # router construction itself failed
    # The deterministic parts are untouched by a narration attempt.
    assert any(s["verdict"] == "bleeding" for s in attribution["scopes"])


def test_narration_fails_closed_when_model_router_import_broken(monkeypatch):
    """The ``from model_router.tasks import ModelTask`` import lives inside a
    try/except in narrate_losses(): if model_router is present but broken
    (import raises) with a non-None router, narration must still degrade to
    {} rather than propagating the ImportError out of this function (which
    would otherwise crash scripts/run_dummy_loss_engine.py::main() before it
    reaches write_report())."""
    rows = _planted_rows()
    attribution = build_loss_attribution(rows, now_iso="2026-07-13T00:00:00+00:00")

    class _NeverCalledRouter:
        async def call(self, *args, **kwargs):  # pragma: no cover
            raise AssertionError("router.call must not be reached if the import breaks first")

    # sys.modules[name] = None is the standard way to force `import name` to
    # raise ImportError without needing an actually-broken package on disk.
    monkeypatch.setitem(sys.modules, "model_router.tasks", None)
    assert narrate_losses(attribution, _NeverCalledRouter()) == {}


def test_narration_fills_field_when_router_succeeds():
    rows = _planted_rows()
    attribution = build_loss_attribution(rows, now_iso="2026-07-13T00:00:00+00:00")

    class _Envelope:
        # CALIBRATION_NOTE's provider schema is {"note": <prose>} (see
        # model_router/providers.py::_TASK_SCHEMAS) -- envelope.content is a
        # JSON string, not the raw prose, so a real router response looks
        # like this.
        content = json.dumps({
            "note": "setup_score looks like the culprit; try repricing low-setup games.",
        })

    class _WorkingRouter:
        async def call(self, *args, **kwargs):
            return _Envelope()

    narration = narrate_losses(attribution, _WorkingRouter())
    assert set(narration) == {"nba|nba|total|pre"}
    note = narration["nba|nba|total|pre"]
    # The extracted value must be plain prose, not the JSON envelope/dict.
    assert isinstance(note, str)
    assert not note.strip().startswith("{")
    assert "setup_score" in note


def test_narration_fails_closed_on_malformed_or_wrong_shape_response():
    rows = _planted_rows()
    attribution = build_loss_attribution(rows, now_iso="2026-07-13T00:00:00+00:00")

    class _NotJsonEnvelope:
        content = "not json at all"

    class _NotJsonRouter:
        async def call(self, *args, **kwargs):
            return _NotJsonEnvelope()

    assert narrate_losses(attribution, _NotJsonRouter()) == {}

    class _WrongShapeEnvelope:
        # A FORECAST_OPINION-shaped envelope (the old, wrong task) has no
        # "note" key -- must fail closed rather than narrating "".
        content = json.dumps({
            "dummy_probability": "0.5", "confidence_score": "0.5", "reasoning": "wrong shape",
        })

    class _WrongShapeRouter:
        async def call(self, *args, **kwargs):
            return _WrongShapeEnvelope()

    assert narrate_losses(attribution, _WrongShapeRouter()) == {}


def _load_script_module():
    """Load scripts/run_dummy_loss_engine.py as a module so tests can call
    its main() directly (with _get_router monkeypatched) instead of only
    exercising narrate_losses() in isolation -- this is the SAME entry point
    the nightly cron uses."""
    script_path = REPO_ROOT / "scripts" / "run_dummy_loss_engine.py"
    spec = importlib.util.spec_from_file_location("run_dummy_loss_engine_under_test", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_still_writes_artifact_when_narration_raises(tmp_path, monkeypatch):
    """If the narration path raises outright when main() runs it (router
    trouble surfacing as an exception rather than a clean None router), the
    deterministic loss_attribution.json artifact must still be written, with
    narration == {}. Exercised through main() -- not narrate_losses() in
    isolation -- because the bug this guards against was main() crashing
    BEFORE write_report()."""
    conn = _random_nba_total_db(rows=60, seed=99)
    db_path = tmp_path / "ledger.db"
    with sqlite3.connect(db_path) as file_conn:
        conn.backup(file_conn)
    conn.close()
    out_path = tmp_path / "loss_attribution.json"

    module = _load_script_module()

    class _RaisingRouter:
        async def call(self, *args, **kwargs):
            raise RuntimeError("router down")

    monkeypatch.setattr(module, "_get_router", lambda: _RaisingRouter())
    monkeypatch.setattr(
        sys, "argv",
        ["run_dummy_loss_engine.py", "--db", str(db_path), "--out", str(out_path)],
    )

    rc = module.main()

    assert rc == 0
    assert out_path.exists()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["narration"] == {}
    assert "family_size" in payload


def test_main_still_writes_artifact_when_model_router_import_broken(tmp_path, monkeypatch):
    """Same entry point as above, but the failure mode is the import inside
    narrate_losses() itself (model_router present but broken) rather than a
    router.call() raise -- the exact scenario named in the review finding."""
    conn = _random_nba_total_db(rows=60, seed=99)
    db_path = tmp_path / "ledger.db"
    with sqlite3.connect(db_path) as file_conn:
        conn.backup(file_conn)
    conn.close()
    out_path = tmp_path / "loss_attribution.json"

    module = _load_script_module()

    class _NeverCalledRouter:
        async def call(self, *args, **kwargs):  # pragma: no cover
            raise AssertionError("router.call must not be reached if the import breaks first")

    monkeypatch.setattr(module, "_get_router", lambda: _NeverCalledRouter())
    monkeypatch.setitem(sys.modules, "model_router.tasks", None)
    monkeypatch.setattr(
        sys, "argv",
        ["run_dummy_loss_engine.py", "--db", str(db_path), "--out", str(out_path)],
    )

    rc = module.main()

    assert rc == 0
    assert out_path.exists()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["narration"] == {}


# --------------------------------------------------------------------- B.3 loop wiring


def _seed_ledger_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL, market_ticker TEXT NOT NULL,
        probability_yes REAL NOT NULL, uncertainty REAL NOT NULL,
        rationale TEXT NOT NULL, features TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL, mode TEXT NOT NULL DEFAULT 'live',
        ingested_at TEXT NOT NULL, ingest_version INTEGER NOT NULL DEFAULT 2
    );
    CREATE TABLE settlements (
        market_ticker TEXT PRIMARY KEY, result_yes INTEGER NOT NULL,
        settled_at TEXT NOT NULL
    );
    """)


def _insert_signal(conn, source, ticker, probability, features, created_at) -> None:
    conn.execute(
        "INSERT INTO signals (source, market_ticker, probability_yes, uncertainty,"
        " rationale, features, created_at, mode, ingested_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (source, ticker, probability, 0.1, "t", json.dumps(features),
         created_at, "live", created_at),
    )


def _nba_total_row_db(
    conn: sqlite3.Connection, index: int, *, expected_total: float, threshold: float,
    result_yes: bool, probability_yes: float,
) -> None:
    when = (START + timedelta(hours=index)).isoformat()
    ticker = f"KXNBATOTAL-26JAN{index:04d}LALBOS-{int(threshold)}"
    features = {
        "sport": "nba", "market_type": "total",
        "expected_home_score": expected_total / 2.0 + 3.0,
        "expected_away_score": expected_total / 2.0 - 3.0,
        "expected_total": expected_total,
        "expected_pace": 99.5,
        "threshold": threshold,
        "margin_model_version": NBA_MODEL_VERSION,
        "home": "LAL", "away": "BOS",
    }
    _insert_signal(conn, "nba_game_total", ticker, probability_yes, features, when)
    _insert_signal(conn, "market_prior", ticker, 0.5, {}, when)
    conn.execute(
        "INSERT INTO settlements (market_ticker, result_yes, settled_at) VALUES (?,?,?)",
        (ticker, int(result_yes), when),
    )


def _random_nba_total_db(rows: int, seed: int) -> sqlite3.Connection:
    rng = random.Random(seed)
    conn = sqlite3.connect(":memory:")
    _seed_ledger_schema(conn)
    offsets = (-15.0, -9.0, -3.0, 3.0, 9.0, 15.0)
    for index in range(rows):
        expected_total = 215.0 + (index % 5) * 3.0
        threshold = expected_total + offsets[index % len(offsets)]
        true_total = rng.gauss(expected_total, 20.5)
        result_yes = true_total > threshold
        probability_yes = total_over_probability(expected_total, 19.5, threshold)
        _nba_total_row_db(
            conn, index, expected_total=expected_total, threshold=threshold,
            result_yes=result_yes, probability_yes=probability_yes,
        )
    conn.commit()
    return conn


def test_tuner_priority_reorders_and_annotates_without_changing_verdict(tmp_path):
    conn = _random_nba_total_db(rows=120, seed=42)

    report_without = tuning_report(
        conn, now_iso="2026-07-13T00:00:00+00:00",
        loss_attribution_path=tmp_path / "does_not_exist.json",
    )

    priority_artifact = {
        "generated_at": "2026-07-13T00:00:00+00:00",
        "settled_rows": 120,
        "scopes": [{
            "scope": "nba|total|pre", "n_clusters": 40, "cluster_edge": -0.42,
            "worst_buckets": [], "verdict": "bleeding",
        }],
        "family_size": {"scopes_evaluated": 1, "buckets_evaluated": 3},
        "narration": {},
    }
    priority_path = tmp_path / "loss_attribution.json"
    priority_path.write_text(json.dumps(priority_artifact), encoding="utf-8")

    report_with = tuning_report(
        conn, now_iso="2026-07-13T00:00:00+00:00", loss_attribution_path=priority_path,
    )

    by_name_without = {p["name"]: p for p in report_without["proposals"]}
    by_name_with = {p["name"]: p for p in report_with["proposals"]}
    assert set(by_name_without) == set(by_name_with)

    for name, proposal_without in by_name_without.items():
        proposal_with = by_name_with[name]
        stripped_without = {k: v for k, v in proposal_without.items() if k != "bleeding_priority"}
        stripped_with = {k: v for k, v in proposal_with.items() if k != "bleeding_priority"}
        assert stripped_with == stripped_without, (
            f"{name}: walk-forward verdict/fields must be byte-identical with"
            " and without the loss-priority list present"
        )

    # The priority list DID change order/annotation: the bleeding tunable
    # (nba_total_sigma_base: specialist=nba, market_type in {"total"}) moves
    # to the front and is flagged.
    assert by_name_without["nba_total_sigma_base"].get("bleeding_priority") is False
    assert by_name_with["nba_total_sigma_base"]["bleeding_priority"] is True
    assert report_with["proposals"][0]["name"] == "nba_total_sigma_base"


def test_loss_priority_orders_worst_scope_first():
    attribution = {
        "scopes": [
            {"scope": "mlb|winner|pre", "cluster_edge": -0.1, "verdict": "bleeding"},
            {"scope": "nba|total|pre", "cluster_edge": -0.5, "verdict": "bleeding"},
            {"scope": "nhl|winner|pre", "cluster_edge": 0.2, "verdict": "not_bleeding"},
        ],
    }
    assert loss_priority(attribution) == ["nba|total|pre", "mlb|winner|pre"]


# --------------------------------------------------------------------- no-mutation


def _hash_source_tree() -> dict[str, str | None]:
    digests: dict[str, str | None] = {}
    for path in sorted((REPO_ROOT / "autonomy").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        digests[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    promotions_path = REPO_ROOT / "runtime" / "autonomy" / "promotions.json"
    digests[str(promotions_path)] = (
        hashlib.sha256(promotions_path.read_bytes()).hexdigest()
        if promotions_path.exists() else None
    )
    return digests


def test_no_source_file_or_promotions_mutated_by_a_full_loss_engine_run(tmp_path):
    """The critical safety property (mirrors the WS-9 tuner's test): running
    the loss engine's nightly entrypoint end-to-end against a real sqlite
    ledger must leave every autonomy/**/*.py file AND
    runtime/autonomy/promotions.json byte-identical (or, if promotions.json
    doesn't exist, still absent). This is a propose-only artifact writer;
    writing anywhere else would be a fail-closed human-gate violation."""
    before = _hash_source_tree()
    assert before, "expected to hash at least one autonomy/*.py file"

    db_path = tmp_path / "ledger.db"
    conn = _random_nba_total_db(rows=60, seed=99)
    with sqlite3.connect(db_path) as file_conn:
        conn.backup(file_conn)
    conn.close()

    out_path = tmp_path / "loss_attribution.json"
    script = REPO_ROOT / "scripts" / "run_dummy_loss_engine.py"
    result = subprocess.run(
        [
            sys.executable, str(script), "--db", str(db_path), "--out", str(out_path),
            "--no-narration",
        ],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert out_path.exists()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert "family_size" in payload
    assert payload["narration"] == {}

    after = _hash_source_tree()
    assert after == before, (
        "a loss-engine run must never mutate any autonomy/*.py source file or"
        " runtime/autonomy/promotions.json"
    )
