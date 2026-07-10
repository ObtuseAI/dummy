"""Paper-only multi-sport Monte Carlo and recursive genome laboratory.

The lab never rewrites source or gains execution authority. It mutates bounded
calibration/policy parameters, evaluates them chronologically by event cluster,
and advances a research champion only with positive paired-bootstrap evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import sqlite3
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autonomy.fees import kalshi_taker_fee_cents
from autonomy.ontology import MarketView, Signal

LAB_VERSION = "sports-recursive-lab-v1"
MIN_SETTLED_OBSERVATIONS = 40
MIN_EVENT_CLUSTERS = 20

ARENA_DIFFICULTIES = {
    "REGULATION": {"shrink": 1.00, "uncertainty": 1.00},
    "FOG_OF_WAR": {"shrink": 0.82, "uncertainty": 1.45},
    "META_SHIFT": {"shrink": 0.68, "uncertainty": 1.70},
    "BOSS_CHAOS": {"shrink": 0.50, "uncertainty": 2.00},
}


def curriculum_stage(observations: int, event_clusters: int) -> str:
    if observations >= 250 and event_clusters >= 80:
        return "BOSS"
    if observations >= 100 and event_clusters >= 40:
        return "ELITE"
    if observations >= MIN_SETTLED_OBSERVATIONS and event_clusters >= MIN_EVENT_CLUSTERS:
        return "VETERAN"
    return "ROOKIE"


def unlocked_mutations(stage: str) -> list[str]:
    skills = ["probability_temperature", "probability_bias"]
    if stage in {"VETERAN", "ELITE", "BOSS"}:
        skills += ["market_blend", "uncertainty_penalty"]
    if stage in {"ELITE", "BOSS"}:
        skills += ["minimum_edge", "maximum_entry_price"]
    return skills


@dataclass(frozen=True)
class SportsGenome:
    probability_temperature: float = 1.0
    probability_bias: float = 0.0
    market_blend: float = 0.20
    uncertainty_penalty: float = 0.75
    minimum_edge: float = 0.055
    maximum_entry_price: int = 80

    @property
    def genome_id(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return "sg-" + hashlib.sha256(payload.encode()).hexdigest()[:12]

    @classmethod
    def from_mapping(cls, value: dict[str, Any] | None) -> "SportsGenome":
        if not value:
            return cls()
        defaults = asdict(cls())
        return cls(**{key: value.get(key, default) for key, default in defaults.items()})


@dataclass(frozen=True)
class SportsObservation:
    observation_id: str
    cycle_id: str
    ticker: str
    event_cluster: str
    sport: str
    market_type: str
    source: str
    model_probability: float
    uncertainty: float
    market_probability: float
    yes_ask: int
    no_ask: int
    observed_at: str
    event_start: str
    sample_size: int
    result_yes: bool | None = None


@dataclass(frozen=True)
class SimulationSummary:
    probability_yes: float
    lower_95: float
    upper_95: float
    scenarios: int
    stress_low: float
    stress_high: float
    seed: int


def _clip(value: float, lower: float = 0.005, upper: float = 0.995) -> float:
    return min(upper, max(lower, float(value)))


def _logit(probability: float) -> float:
    probability = _clip(probability)
    return math.log(probability / (1.0 - probability))


def calibrated_probability(row: SportsObservation, genome: SportsGenome) -> float:
    transformed = 1.0 / (
        1.0 + math.exp(-(_logit(row.model_probability) / genome.probability_temperature
                         + genome.probability_bias))
    )
    return _clip(
        (1.0 - genome.market_blend) * transformed
        + genome.market_blend * row.market_probability
    )


class SportsMonteCarloSimulator:
    """Epistemic-plus-outcome simulation with deterministic replay seeds."""

    @staticmethod
    def simulate(
        probability_yes: float,
        uncertainty: float,
        *,
        scenarios: int = 5000,
        seed: int = 0,
    ) -> SimulationSummary:
        probability = _clip(probability_yes)
        sigma = min(0.45, max(0.01, uncertainty))
        max_variance = probability * (1.0 - probability)
        variance = min(max_variance * 0.90, sigma**2)
        concentration = max(2.0, max_variance / max(1e-6, variance) - 1.0)
        alpha = max(0.1, probability * concentration)
        beta = max(0.1, (1.0 - probability) * concentration)
        rng = random.Random(seed)
        outcomes = 0
        latent: list[float] = []
        for _ in range(max(100, scenarios)):
            sampled_probability = rng.betavariate(alpha, beta)
            latent.append(sampled_probability)
            outcomes += int(rng.random() < sampled_probability)
        latent.sort()
        count = len(latent)
        return SimulationSummary(
            probability_yes=outcomes / count,
            lower_95=latent[int(0.025 * (count - 1))],
            upper_95=latent[int(0.975 * (count - 1))],
            scenarios=count,
            stress_low=_clip(probability - 1.5 * sigma),
            stress_high=_clip(probability + 1.5 * sigma),
            seed=seed,
        )

    @classmethod
    def simulate_arena(
        cls,
        probability_yes: float,
        uncertainty: float,
        *,
        scenarios: int = 500,
        seed: int = 0,
    ) -> dict[str, Any]:
        """Adversarial curriculum arenas inspired by game difficulty modes."""
        arenas: dict[str, Any] = {}
        for index, (name, config) in enumerate(ARENA_DIFFICULTIES.items()):
            stressed_probability = 0.5 + config["shrink"] * (probability_yes - 0.5)
            summary = cls.simulate(
                stressed_probability,
                min(0.45, uncertainty * config["uncertainty"]),
                scenarios=scenarios,
                seed=seed + index * 1009,
            )
            arenas[name] = asdict(summary)
        probabilities = [arena["probability_yes"] for arena in arenas.values()]
        return {
            "arenas": arenas,
            "robust_probability_low": min(probabilities),
            "robust_probability_high": max(probabilities),
            "difficulty_count": len(arenas),
            "deterministic_replay": True,
        }


def paper_action(row: SportsObservation, genome: SportsGenome) -> dict[str, Any]:
    probability = calibrated_probability(row, genome)
    penalty = genome.uncertainty_penalty * row.uncertainty
    yes_probability = _clip(probability - penalty)
    no_probability = _clip(1.0 - probability - penalty)
    yes_fee = kalshi_taker_fee_cents(row.yes_ask, 1, row.ticker)
    no_fee = kalshi_taker_fee_cents(row.no_ask, 1, row.ticker)
    yes_ev = 100.0 * yes_probability - row.yes_ask - yes_fee
    no_ev = 100.0 * no_probability - row.no_ask - no_fee
    side, price, fee, ev = (
        ("yes", row.yes_ask, yes_fee, yes_ev)
        if yes_ev >= no_ev else ("no", row.no_ask, no_fee, no_ev)
    )
    minimum_sample = 3 if row.sport in {"ufc", "f1"} else 10
    sample_ready = row.sample_size >= minimum_sample
    eligible = (
        sample_ready
        and price <= genome.maximum_entry_price
        and ev >= 100.0 * genome.minimum_edge
    )
    return {
        "action": f"PAPER_{side.upper()}" if eligible else "ABSTAIN",
        "side": side,
        "price_cents": price,
        "fee_cents": fee,
        "conservative_ev_cents": ev,
        "calibrated_probability_yes": probability,
        "eligible": eligible,
        "sample_size": row.sample_size,
        "minimum_sample": minimum_sample,
        "blocker": "" if sample_ready else "insufficient participant history",
    }


def _pnl(row: SportsObservation, decision: dict[str, Any]) -> int:
    if not decision["eligible"] or row.result_yes is None:
        return 0
    won = row.result_yes if decision["side"] == "yes" else not row.result_yes
    price = int(decision["price_cents"])
    fee = int(decision["fee_cents"])
    return (100 - price if won else -price) - fee


def evaluate_genome(rows: list[SportsObservation], genome: SportsGenome) -> dict[str, Any]:
    settled = [row for row in rows if row.result_yes is not None]
    if not settled:
        return {
            "genome_id": genome.genome_id, "observations": 0, "event_clusters": 0,
            "brier": None, "log_loss": None, "trades": 0, "net_pnl_cents": 0,
        }
    brier = 0.0
    log_loss = 0.0
    pnl = 0
    trades = 0
    wins = 0
    trade_returns: list[float] = []
    predictions: list[tuple[float, float]] = []
    equity = peak = drawdown = 0
    cluster_scores: dict[str, list[float]] = {}
    for row in sorted(settled, key=lambda item: (item.event_start, item.observed_at)):
        probability = calibrated_probability(row, genome)
        result = 1.0 if row.result_yes else 0.0
        error = (probability - result) ** 2
        predictions.append((probability, result))
        brier += error
        log_loss -= result * math.log(probability) + (1.0 - result) * math.log(1.0 - probability)
        cluster_scores.setdefault(row.event_cluster, []).append(error)
        decision = paper_action(row, genome)
        if decision["eligible"]:
            trades += 1
            trade_pnl = _pnl(row, decision)
            wins += int(trade_pnl > 0)
            trade_returns.append(float(trade_pnl))
            pnl += trade_pnl
            equity += trade_pnl
            peak = max(peak, equity)
            drawdown = max(drawdown, peak - equity)
    count = len(settled)
    bins: list[list[tuple[float, float]]] = [[] for _ in range(10)]
    for probability, result in predictions:
        bins[min(9, int(probability * 10))].append((probability, result))
    calibration_gaps = [
        (len(bucket) / count) * abs(
            sum(item[0] for item in bucket) / len(bucket)
            - sum(item[1] for item in bucket) / len(bucket)
        )
        for bucket in bins if bucket
    ]
    raw_gaps = [
        abs(
            sum(item[0] for item in bucket) / len(bucket)
            - sum(item[1] for item in bucket) / len(bucket)
        )
        for bucket in bins if bucket
    ]
    positives = [probability for probability, result in predictions if result == 1.0]
    negatives = [probability for probability, result in predictions if result == 0.0]
    auc = None
    if positives and negatives:
        comparisons = sum(
            1.0 if positive > negative else 0.5 if positive == negative else 0.0
            for positive in positives for negative in negatives
        )
        auc = comparisons / (len(positives) * len(negatives))
    downside = [value for value in trade_returns if value < 0]
    downside_deviation = (
        math.sqrt(sum(value**2 for value in downside) / len(downside)) if downside else 0.0
    )
    mean_trade = sum(trade_returns) / len(trade_returns) if trade_returns else None
    sortino = (
        mean_trade / downside_deviation
        if mean_trade is not None and downside_deviation > 0 else None
    )
    return {
        "genome_id": genome.genome_id,
        "observations": count,
        "event_clusters": len(cluster_scores),
        "brier": brier / count,
        "log_loss": log_loss / count,
        "trades": trades,
        "net_pnl_cents": pnl,
        "max_drawdown_cents": drawdown,
        "win_rate": wins / trades if trades else None,
        "mean_trade_pnl_cents": mean_trade,
        "sortino": sortino,
        "ece": sum(calibration_gaps),
        "mce": max(raw_gaps) if raw_gaps else None,
        "auc": auc,
        "sharpness": sum(abs(probability - 0.5) for probability, _ in predictions) / count,
        "mean_probability": sum(probability for probability, _ in predictions) / count,
        "cluster_brier": {
            key: sum(values) / len(values) for key, values in cluster_scores.items()
        },
    }


def chronological_folds(
    rows: list[SportsObservation], folds: int = 4,
) -> list[tuple[list[SportsObservation], list[SportsObservation]]]:
    clusters: dict[str, list[SportsObservation]] = {}
    for row in sorted(rows, key=lambda item: (item.event_start, item.observed_at)):
        clusters.setdefault(row.event_cluster, []).append(row)
    ordered = list(clusters.values())
    if len(ordered) < folds + 2:
        return []
    chunk = max(1, len(ordered) // (folds + 1))
    result = []
    for index in range(1, folds + 1):
        split = index * chunk
        train = [row for group in ordered[:split] for row in group]
        test = [row for group in ordered[split: split + chunk] for row in group]
        if train and test:
            result.append((train, test))
    return result


def mutate_population(
    champion: SportsGenome, *, population: int = 32, seed: int = 0,
    stage: str = "BOSS",
) -> list[SportsGenome]:
    rng = random.Random(seed)
    unlocked = set(unlocked_mutations(stage))
    candidates = [champion]
    for _ in range(max(1, population - 1)):
        candidates.append(SportsGenome(
            probability_temperature=(min(1.6, max(0.60,
                champion.probability_temperature + rng.gauss(0.0, 0.10)))
                if "probability_temperature" in unlocked else champion.probability_temperature),
            probability_bias=(min(0.25, max(-0.25,
                champion.probability_bias + rng.gauss(0.0, 0.035)))
                if "probability_bias" in unlocked else champion.probability_bias),
            market_blend=(min(0.75, max(0.0,
                champion.market_blend + rng.gauss(0.0, 0.06)))
                if "market_blend" in unlocked else champion.market_blend),
            uncertainty_penalty=(min(1.75, max(0.25,
                champion.uncertainty_penalty + rng.gauss(0.0, 0.10)))
                if "uncertainty_penalty" in unlocked else champion.uncertainty_penalty),
            minimum_edge=(min(0.18, max(0.025,
                champion.minimum_edge + rng.gauss(0.0, 0.012)))
                if "minimum_edge" in unlocked else champion.minimum_edge),
            maximum_entry_price=(int(min(90, max(55,
                champion.maximum_entry_price + rng.choice((-5, 0, 5)))))
                if "maximum_entry_price" in unlocked else champion.maximum_entry_price),
        ))
    return list({candidate.genome_id: candidate for candidate in candidates}.values())


def paired_cluster_bootstrap(
    champion: dict[str, Any], candidate: dict[str, Any], *,
    samples: int = 2000, seed: int = 0,
) -> dict[str, Any]:
    first = champion.get("cluster_brier") or {}
    second = candidate.get("cluster_brier") or {}
    keys = sorted(set(first) & set(second))
    if not keys:
        return {"mean": None, "lower_95": None, "upper_95": None, "clusters": 0}
    advantages = [float(first[key]) - float(second[key]) for key in keys]
    rng = random.Random(seed)
    means = []
    for _ in range(samples):
        draw = [advantages[rng.randrange(len(advantages))] for _ in advantages]
        means.append(sum(draw) / len(draw))
    means.sort()
    return {
        "mean": sum(advantages) / len(advantages),
        "lower_95": means[int(0.025 * (samples - 1))],
        "upper_95": means[int(0.975 * (samples - 1))],
        "clusters": len(keys),
    }


class RecursiveSportsLab:
    def __init__(self, champions_path: Path, history_path: Path) -> None:
        self.champions_path = champions_path
        self.history_path = history_path
        try:
            self.champions = json.loads(champions_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            self.champions = {}

    def _save(self) -> None:
        self.champions_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.champions_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.champions, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.champions_path)

    def evolve_scope(
        self, scope: str, rows: list[SportsObservation], *, seed: int,
    ) -> dict[str, Any]:
        champion = SportsGenome.from_mapping((self.champions.get(scope) or {}).get("genome"))
        settled = [row for row in rows if row.result_yes is not None]
        clusters = {row.event_cluster for row in settled}
        stage = curriculum_stage(len(settled), len(clusters))
        if len(settled) < MIN_SETTLED_OBSERVATIONS or len(clusters) < MIN_EVENT_CLUSTERS:
            return {
                "scope": scope, "status": "INSUFFICIENT_FORWARD_EVIDENCE",
                "settled_observations": len(settled), "event_clusters": len(clusters),
                "required_observations": MIN_SETTLED_OBSERVATIONS,
                "required_clusters": MIN_EVENT_CLUSTERS,
                "champion": champion.genome_id,
                "curriculum_stage": stage,
                "unlocked_skills": unlocked_mutations(stage),
            }
        folds = chronological_folds(settled)
        if not folds:
            return {"scope": scope, "status": "INSUFFICIENT_TEMPORAL_FOLDS"}
        candidates = mutate_population(champion, seed=seed, stage=stage)
        selection_rows = [row for _train, test in folds for row in test]
        evaluations = [(candidate, evaluate_genome(selection_rows, candidate)) for candidate in candidates]
        viable = [item for item in evaluations if item[1]["trades"] > 0]
        if not viable:
            return {"scope": scope, "status": "NO_EXECUTABLE_PAPER_CANDIDATE"}
        candidate, candidate_eval = min(
            viable,
            key=lambda item: (
                item[1]["brier"], -item[1]["net_pnl_cents"], item[1]["max_drawdown_cents"],
            ),
        )
        champion_eval = evaluate_genome(selection_rows, champion)
        bootstrap = paired_cluster_bootstrap(champion_eval, candidate_eval, seed=seed)
        promotes = (
            candidate.genome_id != champion.genome_id
            and candidate_eval["brier"] <= champion_eval["brier"] - 0.001
            and candidate_eval["net_pnl_cents"] >= champion_eval["net_pnl_cents"]
            and bootstrap["lower_95"] is not None
            and bootstrap["lower_95"] > 0.0
        )
        status = "RESEARCH_CHAMPION_ADVANCED" if promotes else "CHAMPION_RETAINED"
        if promotes:
            self.champions[scope] = {
                "genome": asdict(candidate),
                "genome_id": candidate.genome_id,
                "advanced_at": datetime.now(timezone.utc).isoformat(),
                "execution_authority": False,
                "capital_authority": False,
            }
            self._save()
        record = {
            "lab_version": LAB_VERSION,
            "scope": scope,
            "status": status,
            "champion_before": champion.genome_id,
            "candidate": candidate.genome_id,
            "candidate_evaluation": candidate_eval,
            "champion_evaluation": champion_eval,
            "paired_cluster_bootstrap": bootstrap,
            "curriculum_stage": stage,
            "unlocked_skills": unlocked_mutations(stage),
            "replay_buffer_observations": len(settled),
            "research_mmr": round(
                1000.0
                + 800.0 * (0.25 - candidate_eval["brier"])
                + 0.25 * candidate_eval["net_pnl_cents"],
                2,
            ),
            "execution_authority": False,
            "capital_authority": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with self.history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        return record

    def run(self, rows: list[SportsObservation], *, seed: int = 0) -> dict[str, Any]:
        scopes: dict[str, list[SportsObservation]] = {}
        for row in rows:
            scopes.setdefault(f"{row.sport}:{row.market_type}", []).append(row)
        return {
            "lab_version": LAB_VERSION,
            "scopes": {
                scope: self.evolve_scope(scope, scoped_rows, seed=seed + index)
                for index, (scope, scoped_rows) in enumerate(sorted(scopes.items()))
            },
            "recursive_code_rewrite": False,
            "execution_authority": False,
            "capital_authority": False,
        }


_SCHEMA = """
CREATE TABLE IF NOT EXISTS observations(
 observation_id TEXT PRIMARY KEY, cycle_id TEXT NOT NULL, ticker TEXT NOT NULL,
 event_cluster TEXT NOT NULL, sport TEXT NOT NULL, market_type TEXT NOT NULL,
 source TEXT NOT NULL, model_probability REAL NOT NULL, uncertainty REAL NOT NULL,
 market_probability REAL NOT NULL, yes_ask INTEGER NOT NULL, no_ask INTEGER NOT NULL,
 observed_at TEXT NOT NULL, event_start TEXT NOT NULL, result_yes INTEGER,
 sample_size INTEGER NOT NULL DEFAULT 0, features_json TEXT NOT NULL, rationale TEXT NOT NULL,
 UNIQUE(ticker,source,observed_at)
);
CREATE INDEX IF NOT EXISTS sports_observation_settlement
 ON observations(result_yes,sport,market_type,event_start);
"""


class SportsEvidenceLedger:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, timeout=30)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(_SCHEMA)
        columns = {
            str(row[1]) for row in self.connection.execute("PRAGMA table_info(observations)")
        }
        if "sample_size" not in columns:
            self.connection.execute(
                "ALTER TABLE observations ADD COLUMN sample_size INTEGER NOT NULL DEFAULT 0"
            )
            self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def record(
        self, cycle_id: str, market: MarketView, signal: Signal,
        sport: str, market_type: str,
    ) -> SportsObservation | None:
        if None in (market.yes_bid, market.yes_ask, market.no_bid, market.no_ask):
            return None
        observed_at = signal.created_at
        event_cluster = str(market.raw.get("event_ticker") or market.ticker.rsplit("-", 1)[0])
        market_probability = ((market.yes_bid + market.yes_ask) / 2.0) / 100.0
        observation = SportsObservation(
            observation_id="sports-" + uuid.uuid4().hex[:16],
            cycle_id=cycle_id,
            ticker=market.ticker,
            event_cluster=event_cluster,
            sport=sport,
            market_type=market_type,
            source=signal.source,
            model_probability=signal.probability_yes,
            uncertainty=signal.uncertainty,
            market_probability=market_probability,
            yes_ask=int(market.yes_ask),
            no_ask=int(market.no_ask),
            observed_at=observed_at,
            event_start=str(signal.features.get("event_start") or market.close_time),
            sample_size=max(int(signal.features.get(key) or 0) for key in (
                "sample_games", "sample_fights", "sample_races",
            )),
        )
        self.connection.execute(
            "INSERT OR IGNORE INTO observations("
            "observation_id,cycle_id,ticker,event_cluster,sport,market_type,source,"
            "model_probability,uncertainty,market_probability,yes_ask,no_ask,observed_at,"
            "event_start,result_yes,sample_size,features_json,rationale"
            ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                observation.observation_id, cycle_id, observation.ticker,
                observation.event_cluster, sport, market_type, signal.source,
                observation.model_probability, observation.uncertainty,
                observation.market_probability, observation.yes_ask, observation.no_ask,
                observed_at, observation.event_start, None, observation.sample_size,
                json.dumps(signal.features, sort_keys=True, separators=(",", ":")),
                signal.rationale,
            ),
        )
        self.connection.commit()
        return observation

    def unsettled_tickers(self) -> list[str]:
        return [
            str(row[0]) for row in self.connection.execute(
                "SELECT DISTINCT ticker FROM observations WHERE result_yes IS NULL"
            )
        ]

    def settle(self, ticker: str, result_yes: bool) -> int:
        cursor = self.connection.execute(
            "UPDATE observations SET result_yes=? WHERE ticker=? AND result_yes IS NULL",
            (1 if result_yes else 0, ticker),
        )
        self.connection.commit()
        return cursor.rowcount

    def rows(self, *, earliest_per_ticker_source: bool = True) -> list[SportsObservation]:
        raw = list(self.connection.execute(
            "SELECT * FROM observations ORDER BY event_start,observed_at"
        ))
        seen: set[tuple[str, str]] = set()
        result = []
        for row in raw:
            key = (str(row["ticker"]), str(row["source"]))
            if earliest_per_ticker_source and key in seen:
                continue
            seen.add(key)
            result.append(SportsObservation(
                observation_id=str(row["observation_id"]),
                cycle_id=str(row["cycle_id"]),
                ticker=str(row["ticker"]),
                event_cluster=str(row["event_cluster"]),
                sport=str(row["sport"]),
                market_type=str(row["market_type"]),
                source=str(row["source"]),
                model_probability=float(row["model_probability"]),
                uncertainty=float(row["uncertainty"]),
                market_probability=float(row["market_probability"]),
                yes_ask=int(row["yes_ask"]),
                no_ask=int(row["no_ask"]),
                observed_at=str(row["observed_at"]),
                event_start=str(row["event_start"]),
                sample_size=int(row["sample_size"]),
                result_yes=(None if row["result_yes"] is None else bool(row["result_yes"])),
            ))
        return result


def observation_with_result(row: SportsObservation, result_yes: bool) -> SportsObservation:
    """Pure helper used by chronological simulator tests."""
    return replace(row, result_yes=result_yes)
