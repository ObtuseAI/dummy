"""Run Dummy's public-read-only multi-sport simulation and recursive lab."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.scanner import MarketScanner  # noqa: E402
from autonomy.signals.sports_intelligence import (  # noqa: E402
    BaseballIntelligenceSignal,
    FormulaOneIntelligenceSignal,
    TeamSportsIntelligenceSignal,
    UfcIntelligenceSignal,
    parse_sports_contract,
)
from autonomy.sports.simulation import (  # noqa: E402
    DESIGNATED_SPORTS_PREDICTION_TYPES,
    FORCED_COVERAGE_LANE,
    POLICY_LANE,
    RecursiveSportsLab,
    SportsEvidenceLedger,
    SportsGenome,
    SportsMonteCarloSimulator,
    forced_coverage_action,
    paper_action,
    paper_decision_explanation,
    sports_coverage_assessment,
)

SPORTS_SERIES = [
    "KXMLBGAME", "KXMLBTOTAL", "KXMLBRFI",
    "KXNBAGAME", "KXNBATOTAL",
    "KXNFLGAME", "KXNFLTOTAL",
    "KXNCAAFGAME", "KXNCAAFTOTAL",
    "KXNHLGAME", "KXNHLTOTAL",
    "KXNCAAMBGAME", "KXNCAAMBTOTAL",
    "KXUFCFIGHT", "KXUFCROUNDS", "KXUFCDISTANCE",
    "KXF1RACE",
]


def _public_base() -> str:
    base = os.environ.get("KALSHI_API_BASE", "https://api.elections.kalshi.com").rstrip("/")
    version = os.environ.get("KALSHI_API_VERSION", "trade-api/v2").strip("/")
    return f"{base}/{version}"


def default_fetch_results(tickers: list[str]) -> dict[str, str]:
    import httpx

    results: dict[str, str] = {}
    for start in range(0, min(len(tickers), 200), 50):
        chunk = tickers[start: start + 50]
        response = httpx.get(
            f"{_public_base()}/markets",
            params={"tickers": ",".join(chunk), "limit": len(chunk)},
            timeout=30,
        )
        response.raise_for_status()
        for market in response.json().get("markets", []):
            result = str(market.get("result") or "").lower()
            if result in {"yes", "no"}:
                results[str(market.get("ticker"))] = result
    return results


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _acquire_lock(path: Path, stale_seconds: int) -> int | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and time.time() - path.stat().st_mtime > stale_seconds:
        path.unlink(missing_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return None
    os.write(descriptor, f"pid={os.getpid()} created={time.time()}\n".encode())
    return descriptor


def _append_rotating_jsonl(
    path: Path, row: dict[str, Any], *, max_bytes: int = 5 * 1024 * 1024,
    backups: int = 3,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size >= max(1024, int(max_bytes)):
        for index in range(max(1, int(backups)) - 1, 0, -1):
            source = path.with_name(f"{path.name}.{index}")
            destination = path.with_name(f"{path.name}.{index + 1}")
            if source.exists():
                os.replace(source, destination)
        os.replace(path, path.with_name(f"{path.name}.1"))
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, sort_keys=True, separators=(",", ":")))
        stream.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", type=Path, default=Path("runtime/autonomy/sports_simulation.db"),
    )
    parser.add_argument(
        "--out-dir", type=Path, default=Path("artifacts/dummy/sports_simulation"),
    )
    parser.add_argument("--scenarios", type=int, default=5000)
    parser.add_argument(
        "--lock", type=Path, default=Path("runtime/autonomy/sports_simulation.lock"),
    )
    parser.add_argument("--lock-stale-seconds", type=int, default=1800)
    parser.add_argument("--log", type=Path)
    args = parser.parse_args()

    descriptor = _acquire_lock(
        args.lock, stale_seconds=max(60, int(args.lock_stale_seconds)),
    )
    if descriptor is None:
        print(json.dumps({"status": "SKIPPED_ALREADY_RUNNING", "lock": str(args.lock)}))
        return 0

    now = datetime.now(timezone.utc)
    cycle_id = "sports-" + now.strftime("%Y%m%dT%H%M%S")
    ledger = SportsEvidenceLedger(args.db)
    lab = RecursiveSportsLab(
        Path("runtime/autonomy/sports_champions.json"),
        Path("runtime/autonomy/sports_evolution_history.jsonl"),
    )
    sources = [
        BaseballIntelligenceSignal(), TeamSportsIntelligenceSignal(),
        UfcIntelligenceSignal(), FormulaOneIntelligenceSignal(),
    ]
    errors: list[str] = []
    for source in sources:
        try:
            source.on_cycle_start()
        except Exception as exc:
            errors.append(f"{source.name}:warmup:{type(exc).__name__}")

    try:
        try:
            settlements = default_fetch_results(ledger.unsettled_tickers())
            settlements_recorded = 0
            paper_settlements_recorded = 0
            for ticker, result in settlements.items():
                result_yes = result == "yes"
                settlements_recorded += ledger.settle(ticker, result_yes)
                paper_settlements_recorded += ledger.settle_paper_decisions(
                    ticker, result_yes,
                )
        except Exception as exc:
            settlements_recorded = 0
            paper_settlements_recorded = 0
            errors.append(f"settlement:{type(exc).__name__}")

        markets = MarketScanner(watchlist=SPORTS_SERIES).scan()
        observations = []
        cycle_scope_observations: Counter[str] = Counter()
        forced_decisions_recorded: Counter[str] = Counter()
        policy_decisions_recorded: Counter[str] = Counter()
        for market in markets:
            contract = parse_sports_contract(market)
            if contract is None:
                continue
            for source in sources:
                try:
                    if not source.applicable(market):
                        continue
                    signal = source.generate(market)
                except Exception as exc:
                    errors.append(f"{source.name}:generate:{type(exc).__name__}")
                    continue
                if signal is None:
                    continue
                observation = ledger.record(
                    cycle_id, market, signal, contract.sport, contract.market_type,
                )
                if observation is None:
                    continue
                scope = f"{contract.sport}:{contract.market_type}"
                champion = SportsGenome.from_mapping(
                    (lab.champions.get(scope) or {}).get("genome")
                )
                simulation = SportsMonteCarloSimulator.simulate(
                    signal.probability_yes,
                    signal.uncertainty,
                    scenarios=args.scenarios,
                    seed=int.from_bytes(
                        hashlib.sha256(observation.observation_id.encode()).digest()[:4],
                        "big",
                    ),
                )
                arenas = SportsMonteCarloSimulator.simulate_arena(
                    signal.probability_yes,
                    signal.uncertainty,
                    scenarios=max(200, min(1000, args.scenarios // 4)),
                    seed=int.from_bytes(
                        hashlib.sha256((observation.observation_id + ":arena").encode()).digest()[:4],
                        "big",
                    ),
                )
                decision = paper_action(observation, champion)
                forced_decision = forced_coverage_action(observation, champion)
                scope_key = f"{contract.sport}:{contract.market_type}"
                cycle_scope_observations[scope_key] += 1
                if decision["eligible"]:
                    policy_explanation = paper_decision_explanation(
                        observation, decision, signal.rationale, lane=POLICY_LANE,
                    )
                    if ledger.record_paper_decision(
                        observation, decision, policy_explanation, lane=POLICY_LANE,
                    ):
                        policy_decisions_recorded[scope_key] += 1
                forced_explanation = paper_decision_explanation(
                    observation, forced_decision, signal.rationale,
                    lane=FORCED_COVERAGE_LANE,
                )
                if ledger.record_paper_decision(
                    observation, forced_decision, forced_explanation,
                    lane=FORCED_COVERAGE_LANE,
                ):
                    forced_decisions_recorded[scope_key] += 1
                observations.append({
                    "sport": contract.sport,
                    "market_type": contract.market_type,
                    "ticker": market.ticker,
                    "source": signal.source,
                    "model_probability_yes": signal.probability_yes,
                    "uncertainty": signal.uncertainty,
                    "market_probability_yes": observation.market_probability,
                    "simulation": simulation.__dict__,
                    "adversarial_arenas": arenas,
                    "paper_decision": decision,
                    "forced_coverage_decision": forced_decision,
                    "forced_coverage_explanation": forced_explanation,
                    "explanation": signal.rationale,
                    "challenger_only": True,
                })

        evidence = ledger.rows()
        evolution = lab.run(evidence, seed=int(now.timestamp()))
        picks = [row for row in observations if row["paper_decision"]["eligible"]]
        decision_summary = ledger.paper_decision_summary()
        tracked_forced = {
            f"{row['sport']}:{row['market_type']}": int(row["decisions"])
            for row in decision_summary["lanes"]
            if str(row["lane"]) == FORCED_COVERAGE_LANE
        }
        coverage_matrix = []
        for sport, market_type in DESIGNATED_SPORTS_PREDICTION_TYPES:
            scope_key = f"{sport}:{market_type}"
            observed = int(cycle_scope_observations[scope_key])
            tracked = int(tracked_forced.get(scope_key, 0))
            assessment = sports_coverage_assessment(sport, market_type, observed)
            coverage_matrix.append({
                "sport": sport,
                "market_type": market_type,
                "scope": scope_key,
                **assessment,
                "markets_observed_this_cycle": observed,
                "forced_trades_recorded_this_cycle": int(
                    forced_decisions_recorded[scope_key]
                ),
                "policy_trades_recorded_this_cycle": int(
                    policy_decisions_recorded[scope_key]
                ),
                "tracked_forced_trades": tracked,
                "counts_toward_promotion": False,
            })
        report = {
            "report_name": "DUMMY_MULTI_SPORT_RECURSIVE_SIMULATION",
            "lab_version": evolution["lab_version"],
            "cycle_id": cycle_id,
            "started_at": now.isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "status": "CYCLE_OK" if not errors else "CYCLE_OK_WITH_SOURCE_ERRORS",
            "markets_seen": len(markets),
            "observations_written": len(observations),
            "paper_picks": len(picks),
            "policy_paper_trades_recorded": sum(policy_decisions_recorded.values()),
            "forced_paper_trades_recorded": sum(forced_decisions_recorded.values()),
            "settlements_recorded": settlements_recorded,
            "paper_settlements_recorded": paper_settlements_recorded,
            "coverage": {
                "team_sports": ["MLB", "NFL", "NCAAF", "NHL", "NBA", "NCAAB"],
                "combat": ["UFC"],
                "motorsport": ["FORMULA_ONE"],
                "market_types": [
                    "WINNER", "GAME_TOTAL", "MLB_YRFI_NRFI", "UFC_ROUND_TOTAL",
                    "UFC_DISTANCE", "F1_RACE_WINNER",
                ],
            },
            "game_engine": {
                "deterministic_replay_buffer": True,
                "mmr_progression": True,
                "curriculum_tiers": ["ROOKIE", "VETERAN", "ELITE", "BOSS"],
                "adversarial_arenas": list((
                    "REGULATION", "FOG_OF_WAR", "META_SHIFT", "BOSS_CHAOS",
                )),
                "skill_tree_unlocks_require_settled_evidence": True,
                "self_play_scope": "bounded genome tournament",
            },
            "evolution": evolution,
            "paper_decision_summary": decision_summary,
            "forced_coverage": {
                "lane": FORCED_COVERAGE_LANE,
                "designated_prediction_types": len(DESIGNATED_SPORTS_PREDICTION_TYPES),
                "types_observed_this_cycle": sum(
                    int(row["markets_observed_this_cycle"] > 0)
                    for row in coverage_matrix
                ),
                "types_covered_without_gap": sum(
                    int(not row["is_coverage_gap"])
                    for row in coverage_matrix
                ),
                "coverage_gap_count": sum(
                    int(row["is_coverage_gap"])
                    for row in coverage_matrix
                ),
                "coverage_gaps": [
                    row["scope"] for row in coverage_matrix
                    if row["is_coverage_gap"]
                ],
                "matrix": coverage_matrix,
                "real_listed_markets_only": True,
                "fabricated_trades": False,
                "counts_toward_promotion": False,
            },
            "active_paper_trades": ledger.recent_paper_decisions(
                status="OPEN", limit=100,
            ),
            "recent_paper_settlements": ledger.recent_paper_decisions(
                status="SETTLED", limit=50,
            ),
            "picks": picks[:100],
            "observations": observations[:250],
            "errors": errors,
            "authority": {
                "public_get_only": True,
                "credentials_loaded": False,
                "broker_contacted": False,
                "execution_authority": False,
                "capital_authority": False,
                "recursive_code_rewrite": False,
                "challenger_only": True,
                "forced_coverage_counts_toward_promotion": False,
            },
        }
        stamp = report["completed_at"].replace(":", "").replace("-", "").replace("+0000", "Z")
        report_path = args.out_dir / f"SPORTS_SIMULATION_{stamp}.json"
        _atomic_json(report_path, report)
        _atomic_json(args.out_dir / "SPORTS_SIMULATION_LATEST.json", {
            **report, "report_path": str(report_path.resolve()),
        })
        _atomic_json(Path("runtime/autonomy/sports_simulation_latest.json"), {
            "report_name": report["report_name"],
            "report_path": str(report_path.resolve()),
            "cycle_id": cycle_id,
            "started_at": report["started_at"],
            "completed_at": report["completed_at"],
            "status": report["status"],
            "markets_seen": report["markets_seen"],
            "observations_written": report["observations_written"],
            "paper_picks": report["paper_picks"],
            "policy_paper_trades_recorded": report["policy_paper_trades_recorded"],
            "forced_paper_trades_recorded": report["forced_paper_trades_recorded"],
            "settlements_recorded": report["settlements_recorded"],
            "paper_settlements_recorded": report["paper_settlements_recorded"],
            "paper_decision_summary": decision_summary,
            "forced_coverage": report["forced_coverage"],
            "active_paper_trades": report["active_paper_trades"],
            "recent_paper_settlements": report["recent_paper_settlements"],
            "errors": errors,
            "authority": report["authority"],
        })
        console = {
            "status": report["status"], "cycle_id": cycle_id,
            "markets_seen": len(markets), "observations_written": len(observations),
            "paper_picks": len(picks), "settlements_recorded": settlements_recorded,
            "policy_paper_trades_recorded": sum(policy_decisions_recorded.values()),
            "forced_paper_trades_recorded": sum(forced_decisions_recorded.values()),
            "paper_settlements_recorded": paper_settlements_recorded,
            "report_path": str(report_path.resolve()), "errors": errors,
            "authority": report["authority"],
        }
        if args.log is not None:
            _append_rotating_jsonl(args.log, console)
        print(json.dumps(console, sort_keys=True))
        return 0
    finally:
        ledger.close()
        os.close(descriptor)
        args.lock.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
