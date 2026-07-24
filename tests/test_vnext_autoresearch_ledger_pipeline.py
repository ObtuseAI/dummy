from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

from dummy.autoresearch.candidate_replay import (
    GenomeReplayPolicy,
    materialize_task_suite,
    measure_genome_complexity,
)
from dummy.autoresearch.campaign import run_loop1_campaign
from dummy.autoresearch.ledger_pipeline import (
    build_ledger_partition_plan,
    load_ledger_evidence,
)
from dummy.autoresearch.forward_paper import (
    build_forward_registry,
    grade_forward_observations,
    issue_forward_observations,
)
from dummy.autoresearch.models import EvaluationPartition
from dummy.autoresearch.operational_ignition import (
    operational_ignition_report,
    record_campaign_ignition_trial,
)
from dummy.genome import (
    GeneCategory,
    MutationLevel,
    MutationOperation,
    MutationOperator,
    pilot_genomes,
    propose_mutation,
)


NOW = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)


def _ledger(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE decisions (
            decision_id TEXT PRIMARY KEY, market_ticker TEXT NOT NULL,
            action TEXT NOT NULL, side TEXT NOT NULL, price_cents INTEGER NOT NULL,
            count INTEGER NOT NULL, probability_yes REAL NOT NULL,
            forecast_uncertainty REAL NOT NULL, market_implied_yes REAL,
            sources_used TEXT NOT NULL, abstain_reason TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE settlements (
            market_ticker TEXT PRIMARY KEY, result_yes INTEGER NOT NULL,
            settled_at TEXT NOT NULL
        );
        CREATE TABLE outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, decision_id TEXT NOT NULL,
            kind TEXT NOT NULL, fill_count INTEGER NOT NULL DEFAULT 0,
            pnl_cents INTEGER
        );
        """
    )
    for day in range(6):
        for index in range(4):
            result = index % 2 == 0
            decision_id = f"decision-{day}-{index}"
            ticker = f"KXBTC15M-26JUL{day + 1:02d}1200-{index:02d}"
            created = NOW + timedelta(days=day, minutes=index)
            settled = created + timedelta(hours=1)
            forecast = 0.70 if result else 0.30
            market = 0.50
            action = "BUY_YES" if result else "BUY_NO"
            connection.execute(
                "INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    decision_id,
                    ticker,
                    action,
                    "yes" if result else "no",
                    50,
                    1,
                    forecast,
                    0.10,
                    market,
                    json.dumps({"market_prior": 0.5, "crypto_spot_vol": 0.5}),
                    "",
                    created.isoformat(),
                ),
            )
            connection.execute(
                "INSERT INTO settlements VALUES (?,?,?)",
                (ticker, int(result), settled.isoformat()),
            )
            if day == 0 and index == 0:
                connection.execute(
                    "INSERT INTO outcomes(decision_id,kind,fill_count,pnl_cents) VALUES (?,?,?,?)",
                    (decision_id, "FILLED", 1, None),
                )
                connection.execute(
                    "INSERT INTO outcomes(decision_id,kind,fill_count,pnl_cents) VALUES (?,?,?,?)",
                    (decision_id, "SETTLED_WIN", 1, 50),
                )
    connection.commit()
    connection.close()


def _base_and_candidate():
    base = next(
        genome for genome in pilot_genomes() if genome.market_type == "15m_direction"
    )
    proposal = propose_mutation(
        base,
        level=MutationLevel.PARAMETERS,
        operations=(
            MutationOperation(
                operator=MutationOperator.SET,
                gene_name="synthesis.market_prior_weight",
                category=GeneCategory.MARKET_PRIOR_WEIGHT,
                value=0.60,
                gene_version="real-replay-test-v1",
                rationale="test a stronger market anchor",
            ),
        ),
        target_paths=("dummy/forecasting/research/test-anchor.json",),
        created_at=NOW,
        evidence_ids=("visible-ledger-fixture",),
    )
    assert proposal.candidate_genome is not None
    return base, proposal.candidate_genome


def test_real_ledger_compiler_is_read_only_chronological_and_candidate_independent(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ledger.db"
    _ledger(path)
    before = path.read_bytes()
    rows = load_ledger_evidence(path, ticker_prefix="KXBTC15M")
    plan = build_ledger_partition_plan(rows, scope="crypto|btc|15m_direction|15m")
    base, candidate = _base_and_candidate()
    policy = GenomeReplayPolicy.from_genomes(
        candidate=candidate,
        base=base,
        lineage_id="market-prior-anchored",
    )
    suite = materialize_task_suite(rows, plan=plan, policy=policy)

    assert path.read_bytes() == before
    assert len(rows) == 24
    assert plan.public_manifest()["item_assignments_exposed"] is False
    assert set(suite.partition_manifest()) == {
        partition.value for partition in EvaluationPartition
    }
    partition_dates = {
        partition: {task.decision_at.date() for task in suite.partition(partition)}
        for partition in EvaluationPartition
    }
    assert all(
        partition_dates[left].isdisjoint(partition_dates[right])
        for left in EvaluationPartition
        for right in EvaluationPartition
        if left is not right
    )
    assert all(
        task.close_time_provenance == "SETTLEMENT_RECEIPT_UPPER_BOUND"
        for task in suite.tasks
    )


def test_replay_inherits_fill_only_for_the_exact_recorded_decision(tmp_path: Path) -> None:
    path = tmp_path / "ledger.db"
    _ledger(path)
    rows = load_ledger_evidence(path, ticker_prefix="KXBTC15M")
    plan = build_ledger_partition_plan(rows, scope="crypto|btc|15m_direction|15m")
    base, candidate = _base_and_candidate()
    policy = GenomeReplayPolicy.from_genomes(
        candidate=candidate,
        base=base,
        lineage_id="market-prior-anchored",
    )
    suite = materialize_task_suite(rows, plan=plan, policy=policy)
    filled = next(task for task in suite.tasks if task.incumbent_fill_verified)
    assert filled.candidate_fill_verified is True
    assert filled.candidate_pnl_cents == filled.incumbent_pnl_cents == 50
    assert filled.candidate_counterfactual_pnl_cents == 0
    complexity = measure_genome_complexity(base, candidate)
    assert complexity.changed_modules == 1
    assert complexity.added_dependencies == 0


def test_loop1_campaign_explores_each_lineage_once_and_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "ledger.db"
    _ledger(path)
    rows = load_ledger_evidence(path, ticker_prefix="KXBTC15M")
    plan = build_ledger_partition_plan(rows, scope="crypto|btc|15m_direction|15m")
    base, _ = _base_and_candidate()
    first = run_loop1_campaign(
        rows=rows,
        plan=plan,
        base_genome=base,
        created_at=NOW + timedelta(days=10),
        per_experiment_compute_budget=100.0,
    )
    second = run_loop1_campaign(
        rows=rows,
        plan=plan,
        base_genome=base,
        created_at=NOW + timedelta(days=10),
        per_experiment_compute_budget=100.0,
    )
    assert first == second
    assert first["genuine_private_candidate_trials"] == 5
    assert {row["lineage_id"] for row in first["candidates"]} == {
        "abstention-first",
        "calibration-first",
        "crypto-liquidity",
        "execution-aware",
        "market-prior-anchored",
    }
    assert first["best_forward_candidate_id"] is None
    assert first["performance_claim_supported"] is False
    assert first["unavailable_lineages"][0]["lineage_id"] == "mlb-simulation"


def test_forward_paper_issues_before_settlement_and_grades_without_orders(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ledger.db"
    _ledger(path)
    base, candidate = _base_and_candidate()
    epoch = NOW + timedelta(days=6)
    campaign = {
        "campaign_id": "campaign-forward-test",
        "evidence_cutoff": epoch.isoformat(),
        "scope": "crypto|btc|15m_direction|15m",
        "best_forward_candidate_id": candidate.genome_id,
        "candidates": [
            {
                "candidate_genome": candidate.to_dict(),
                "lineage_id": "market-prior-anchored",
                "forward_paper_eligible": True,
            }
        ],
    }
    registry = build_forward_registry(
        campaign,
        base_genome=base,
        ticker_prefix="KXBTC15M",
    )
    connection = sqlite3.connect(path)
    for index in range(4):
        result = index % 2 == 0
        decision_id = f"forward-{index}"
        ticker = f"KXBTC15M-26JUL081200-{index:02d}"
        created = NOW + timedelta(days=7, minutes=index)
        connection.execute(
            "INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                decision_id,
                ticker,
                "BUY_YES" if result else "BUY_NO",
                "yes" if result else "no",
                50,
                1,
                0.70 if result else 0.30,
                0.10,
                0.50,
                json.dumps({"market_prior": 0.5, "crypto_spot_vol": 0.5}),
                "",
                created.isoformat(),
            ),
        )
    connection.commit()
    connection.close()

    observation_path = tmp_path / "forward_observations.jsonl"
    issued_at = NOW + timedelta(days=7, minutes=30)
    issued = issue_forward_observations(
        registry,
        ledger_path=path,
        observation_ledger_path=observation_path,
        issued_at=issued_at,
    )
    assert issued["new_observations"] == 4
    assert issued["orders_placed"] is False
    assert grade_forward_observations(
        registry,
        ledger_path=path,
        observation_ledger_path=observation_path,
    )["forward_paper_candidate_settlements"] == 0

    connection = sqlite3.connect(path)
    for index in range(4):
        result = index % 2 == 0
        decision_id = f"forward-{index}"
        ticker = f"KXBTC15M-26JUL081200-{index:02d}"
        settled = NOW + timedelta(days=7, hours=2, minutes=index)
        connection.execute(
            "INSERT INTO settlements VALUES (?,?,?)",
            (ticker, int(result), settled.isoformat()),
        )
        if index == 0:
            connection.execute(
                "INSERT INTO outcomes(decision_id,kind,fill_count,pnl_cents) VALUES (?,?,?,?)",
                (decision_id, "FILLED", 1, None),
            )
            connection.execute(
                "INSERT INTO outcomes(decision_id,kind,fill_count,pnl_cents) VALUES (?,?,?,?)",
                (decision_id, "SETTLED_WIN", 1, 50),
            )
    connection.commit()
    connection.close()
    graded = grade_forward_observations(
        registry,
        ledger_path=path,
        observation_ledger_path=observation_path,
    )
    assert graded["forward_paper_candidate_settlements"] == 4
    assert graded["verified_settled_fills"] == 1
    assert graded["ready_for_human_promotion_review"] is False
    assert graded["orders_placed"] is False
    assert graded["execution_authority"] is False


def test_operational_ignition_records_one_campaign_once_and_blocks_level_two(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ledger.db"
    _ledger(path)
    rows = load_ledger_evidence(path, ticker_prefix="KXBTC15M")
    plan = build_ledger_partition_plan(rows, scope="crypto|btc|15m_direction|15m")
    base, _ = _base_and_candidate()
    campaign = run_loop1_campaign(
        rows=rows,
        plan=plan,
        base_genome=base,
        created_at=NOW + timedelta(days=10),
        per_experiment_compute_budget=100.0,
    )
    trial_path = tmp_path / "ignition_trials.jsonl"
    first = record_campaign_ignition_trial(campaign, trial_ledger_path=trial_path)
    second = record_campaign_ignition_trial(campaign, trial_ledger_path=trial_path)
    assert first.trial_id == second.trial_id
    report = operational_ignition_report(
        trial_ledger_path=trial_path,
        forward_report={
            "ready_for_human_promotion_review": False,
            "forward_paper_candidate_settlements": 0,
            "event_clusters": 0,
            "verified_settled_fills": 0,
        },
    )
    assert report["trial_count"] == 1
    assert report["highest_supported_recursive_improvement_level"] == 0
    assert report["level1_net_positive_self_improvement_supported"] is False
    assert report["level2_matched_ab_test"]["eligible"] is False
    assert report["execution_authority"] is False


def test_autoresearch_cycle_cli_emits_complete_fail_closed_bundle(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.db"
    _ledger(ledger)
    output = tmp_path / "autoresearch"
    script = Path(__file__).parents[1] / "scripts" / "run_dummy_autoresearch.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--ledger",
            str(ledger),
            "--output-dir",
            str(output),
            "--issued-at",
            (NOW + timedelta(days=20)).isoformat(),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    summary = json.loads(result.stdout)
    assert summary["private_trials"] == 5
    assert summary["orders_placed"] is False
    assert summary["execution_authority"] is False
    assert (output / "campaign_report.json").exists()
    assert (output / "forward_registry.json").exists()
    assert (output / "forward_report.json").exists()
    assert (output / "ignition_report.json").exists()


# --- Wave-84: unattended-execution safety for the DummyAutoresearch task ----

RUNNER = Path(__file__).parents[1] / "scripts" / "run_dummy_autoresearch.py"


def _run_runner(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNNER), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _status(output: Path) -> dict:
    path = output.parent / "autoresearch_status.json"
    assert path.exists(), "runner must always leave a status artifact"
    return json.loads(path.read_text(encoding="utf-8"))


def test_runner_status_artifact_is_written_beside_the_output_dir(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.db"
    _ledger(ledger)
    output = tmp_path / "autoresearch"

    result = _run_runner(
        "--ledger", str(ledger),
        "--output-dir", str(output),
        "--issued-at", (NOW + timedelta(days=20)).isoformat(),
    )

    assert result.returncode == 0, result.stderr
    status = _status(output)
    assert status["status"] == "OK"
    assert status["task"] == "DummyAutoresearch"
    # Timestamps the watchdog can use for staleness.
    assert status["generated_at"] and status["last_success_at"]
    assert status["duration_seconds"] >= 0
    assert status["ledger_access"] == "read-only"
    assert status["network_calls"] is False
    assert status["orders_placed"] is False
    assert status["execution_authority"] is False
    assert status["capital_authority"] is False
    assert status["automatic_promotion"] is False
    assert status["trial_ledger_rotation"]["truncated"] is False


def test_runner_is_fail_soft_when_the_ledger_is_missing(tmp_path: Path) -> None:
    output = tmp_path / "autoresearch"

    result = _run_runner(
        "--ledger", str(tmp_path / "absent.db"),
        "--output-dir", str(output),
    )

    # A missing ledger is a skip, not a crash and not a fabricated cycle.
    assert result.returncode == 0
    assert "Traceback" not in result.stderr
    status = _status(output)
    assert status["status"] == "SKIPPED_INSUFFICIENT_EVIDENCE"
    assert "absent.db" in status["detail"]
    assert status["last_success_at"] is None


def test_runner_deadline_defers_instead_of_overrunning(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.db"
    _ledger(ledger)
    output = tmp_path / "autoresearch"

    result = _run_runner(
        "--ledger", str(ledger),
        "--output-dir", str(output),
        "--issued-at", (NOW + timedelta(days=20)).isoformat(),
        "--max-seconds", "0.001",
    )

    assert result.returncode == 0
    status = _status(output)
    assert status["status"] == "DEFERRED_RUN_DEADLINE"
    assert status["max_seconds"] == 0.001


def test_runner_preserves_last_success_across_a_later_skip(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.db"
    _ledger(ledger)
    output = tmp_path / "autoresearch"
    _run_runner(
        "--ledger", str(ledger),
        "--output-dir", str(output),
        "--issued-at", (NOW + timedelta(days=20)).isoformat(),
    )
    success_at = _status(output)["last_success_at"]
    assert success_at

    _run_runner("--ledger", str(tmp_path / "absent.db"), "--output-dir", str(output))

    # A later skip must not erase the evidence of the last real run.
    assert _status(output)["status"] == "SKIPPED_INSUFFICIENT_EVIDENCE"
    assert _status(output)["last_success_at"] == success_at


def test_trial_ledger_is_tail_capped_and_discloses_the_drop(tmp_path: Path) -> None:
    from importlib import util as _util

    spec = _util.spec_from_file_location("dummy_autoresearch_runner", RUNNER)
    module = _util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    trials = tmp_path / "ignition_trials.jsonl"
    trials.write_text(
        "".join(f'{{"trial": {index}}}\n' for index in range(10)), encoding="utf-8",
    )

    report = module.cap_trial_ledger(trials, 4)

    assert report["truncated"] is True
    assert report["lines_dropped"] == 6
    assert report["lines_retained"] == 4
    kept = trials.read_text(encoding="utf-8").splitlines()
    # Newest trials are the ones kept.
    assert json.loads(kept[0])["trial"] == 6
    assert json.loads(kept[-1])["trial"] == 9
    # Disabled cap leaves the file alone.
    assert module.cap_trial_ledger(trials, 0)["truncated"] is False


def test_runner_defaults_never_target_the_live_runtime_from_a_test_dir(
    tmp_path: Path,
) -> None:
    from importlib import util as _util

    spec = _util.spec_from_file_location("dummy_autoresearch_runner", RUNNER)
    module = _util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    # Production default lands where the watchdog reads task artifacts...
    assert module.default_status_path(module.DEFAULT_OUTPUT_DIR).name == (
        "autoresearch_status.json"
    )
    assert module.default_status_path(module.DEFAULT_OUTPUT_DIR).parent.name == (
        "autonomy"
    )
    # ...and an ad-hoc output dir keeps its status inside that tree.
    assert module.default_status_path(tmp_path / "autoresearch").parent == tmp_path
