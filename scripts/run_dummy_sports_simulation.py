"""Run Dummy's public-read-only multi-sport simulation and recursive lab."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
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
    RecursiveSportsLab,
    SportsEvidenceLedger,
    SportsGenome,
    SportsMonteCarloSimulator,
    paper_action,
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", type=Path, default=Path("runtime/autonomy/sports_simulation.db"),
    )
    parser.add_argument(
        "--out-dir", type=Path, default=Path("artifacts/dummy/sports_simulation"),
    )
    parser.add_argument("--scenarios", type=int, default=5000)
    args = parser.parse_args()

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
            settlements_recorded = sum(
                ledger.settle(ticker, result == "yes")
                for ticker, result in settlements.items()
            )
        except Exception as exc:
            settlements_recorded = 0
            errors.append(f"settlement:{type(exc).__name__}")

        markets = MarketScanner(watchlist=SPORTS_SERIES).scan()
        observations = []
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
                    "explanation": signal.rationale,
                    "challenger_only": True,
                })

        evidence = ledger.rows()
        evolution = lab.run(evidence, seed=int(now.timestamp()))
        picks = [row for row in observations if row["paper_decision"]["eligible"]]
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
            "settlements_recorded": settlements_recorded,
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
            },
        }
        stamp = report["completed_at"].replace(":", "").replace("-", "").replace("+0000", "Z")
        report_path = args.out_dir / f"SPORTS_SIMULATION_{stamp}.json"
        _atomic_json(report_path, report)
        _atomic_json(args.out_dir / "SPORTS_SIMULATION_LATEST.json", {
            **report, "report_path": str(report_path.resolve()),
        })
        print(json.dumps({
            "status": report["status"], "cycle_id": cycle_id,
            "markets_seen": len(markets), "observations_written": len(observations),
            "paper_picks": len(picks), "settlements_recorded": settlements_recorded,
            "report_path": str(report_path.resolve()), "errors": errors,
            "authority": report["authority"],
        }, indent=2, sort_keys=True))
        return 0
    finally:
        ledger.close()


if __name__ == "__main__":
    raise SystemExit(main())
