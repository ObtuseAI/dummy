"""Deterministic multi-objective metrics shared by protected evaluators."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

from dummy.truth import clustered_mean_test

from .complexity_gate import ComplexityDecision
from .models import MetricVector, ResearchTask
from .reward_hacking_detector import RewardHackAudit


_EPSILON = 1e-12


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _brier(probability: float, outcome: float) -> float:
    return (probability - outcome) ** 2


def _log_loss(probability: float, outcome: float) -> float:
    bounded = min(1.0 - _EPSILON, max(_EPSILON, probability))
    return -(outcome * math.log(bounded) + (1.0 - outcome) * math.log(1.0 - bounded))


def _calibration_error(
    probabilities: list[float], outcomes: list[float], bins: int = 10
) -> float:
    grouped: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for predicted, outcome in zip(probabilities, outcomes, strict=True):
        index = min(bins - 1, int(predicted * bins))
        grouped[index].append((predicted, outcome))
    count = len(probabilities)
    if not count:
        return 1.0
    return sum(
        len(rows)
        / count
        * abs(_mean([row[0] for row in rows]) - _mean([row[1] for row in rows]))
        for rows in grouped.values()
    )


def _maximum_drawdown(pnl: list[int]) -> float:
    equity = 0
    peak = 0
    drawdown = 0
    for value in pnl:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return drawdown / 100.0


@dataclass(frozen=True, slots=True)
class MetricComputation:
    metrics: MetricVector
    fitness: float
    confidence_interval: tuple[float, float] | None
    raw_brier_improvement: float
    candidate_calibration_error: float
    incumbent_calibration_error: float
    candidate_compute_efficiency: float
    incumbent_compute_efficiency: float
    abstention_rate: float
    contested_count: int


def compute_metrics(
    tasks: tuple[ResearchTask, ...],
    *,
    complexity: ComplexityDecision,
    reward_audit: RewardHackAudit,
) -> MetricComputation:
    forecast_tasks = tuple(item for item in tasks if not item.candidate_abstained)
    candidate_probabilities = [
        float(item.candidate_probability) for item in forecast_tasks
    ]
    incumbent_probabilities = [item.incumbent_probability for item in forecast_tasks]
    outcomes = [item.outcome for item in forecast_tasks]
    brier_gains = [
        _brier(task.incumbent_probability, task.outcome)
        - _brier(float(task.candidate_probability), task.outcome)
        for task in forecast_tasks
    ]
    contested = tuple(
        task
        for task in forecast_tasks
        if abs(float(task.candidate_probability) - task.market_prior_probability) >= 0.05
    )
    contested_gains = [
        _brier(task.incumbent_probability, task.outcome)
        - _brier(float(task.candidate_probability), task.outcome)
        for task in contested
    ]
    log_gains = [
        _log_loss(task.incumbent_probability, task.outcome)
        - _log_loss(float(task.candidate_probability), task.outcome)
        for task in forecast_tasks
    ]
    candidate_calibration = _calibration_error(candidate_probabilities, outcomes)
    incumbent_calibration = _calibration_error(incumbent_probabilities, outcomes)
    calibration_improvement = incumbent_calibration - candidate_calibration
    useful_sharpness = _mean(
        [abs(value - 0.5) for value in candidate_probabilities]
    ) - _mean([abs(value - 0.5) for value in incumbent_probabilities])

    transfer_rows: dict[str, list[float]] = defaultdict(list)
    for task, gain in zip(forecast_tasks, brier_gains, strict=True):
        transfer_rows[task.transfer_group].append(gain)
    cross_regime_transfer = (
        min(_mean(values) for values in transfer_rows.values())
        if transfer_rows
        else -1.0
    )
    abstention_scores = [
        1.0 if task.abstention_was_correct else -1.0
        for task in tasks
        if task.candidate_abstained
    ]
    abstention_rate = sum(item.candidate_abstained for item in tasks) / len(tasks)
    abstention_quality = _mean(abstention_scores) - max(0.0, abstention_rate - 0.5)

    candidate_cost = _mean([item.candidate_cost_microunits for item in tasks])
    incumbent_cost = _mean([item.incumbent_cost_microunits for item in tasks])
    raw_brier_improvement = _mean(brier_gains)
    relative_cost = candidate_cost / incumbent_cost
    information_per_cost = raw_brier_improvement / relative_cost

    fill_tasks = tuple(
        item
        for item in tasks
        if item.candidate_fill_verified or item.incumbent_fill_verified
    )
    fill_conditioned_improvement = _mean(
        [
            (item.candidate_pnl_cents - item.incumbent_pnl_cents) / 100.0
            for item in fill_tasks
        ]
    )
    drawdown = _maximum_drawdown(
        [item.candidate_pnl_cents for item in tasks if item.candidate_fill_verified]
    )
    duplicated_family_rows = sum(
        len(item.source_family_ids) != len(set(item.source_family_ids))
        for item in tasks
    )
    source_correlation_penalty = duplicated_family_rows / len(tasks)
    replay_instability = sum(not item.replay_stable for item in tasks) / len(tasks)

    candidate_mean_brier = _mean(
        [
            _brier(float(item.candidate_probability), item.outcome)
            for item in forecast_tasks
        ]
    )
    incumbent_mean_brier = _mean(
        [_brier(item.incumbent_probability, item.outcome) for item in forecast_tasks]
    )
    candidate_compute = _mean([item.candidate_compute_units for item in tasks])
    incumbent_compute = _mean([item.incumbent_compute_units for item in tasks])
    candidate_compute_efficiency = (1.0 - candidate_mean_brier) / candidate_compute
    incumbent_compute_efficiency = (1.0 - incumbent_mean_brier) / incumbent_compute

    metric_vector = MetricVector(
        contested_brier_improvement=_mean(contested_gains),
        log_loss_improvement=_mean(log_gains),
        calibration_improvement=calibration_improvement,
        useful_sharpness=useful_sharpness,
        fill_conditioned_improvement=fill_conditioned_improvement,
        cross_regime_transfer=cross_regime_transfer,
        abstention_quality=abstention_quality,
        information_per_cost=information_per_cost,
        drawdown_penalty=drawdown,
        complexity_penalty=complexity.score,
        source_correlation_penalty=source_correlation_penalty,
        reward_hacking_penalty=float(len(reward_audit.findings)),
        replay_instability=replay_instability,
    )
    fitness = (
        3.0 * metric_vector.contested_brier_improvement
        + 1.5 * metric_vector.log_loss_improvement
        + metric_vector.calibration_improvement
        + 0.5 * metric_vector.useful_sharpness
        + 0.5 * metric_vector.fill_conditioned_improvement
        + metric_vector.cross_regime_transfer
        + 0.5 * metric_vector.abstention_quality
        + 0.25 * metric_vector.information_per_cost
        - metric_vector.drawdown_penalty
        - 0.02 * metric_vector.complexity_penalty
        - metric_vector.source_correlation_penalty
        - 2.0 * metric_vector.reward_hacking_penalty
        - metric_vector.replay_instability
    )
    inference_rows = tuple(
        (
            task.event_cluster_id,
            _brier(task.incumbent_probability, task.outcome)
            - _brier(float(task.candidate_probability), task.outcome),
        )
        for task in contested
    )
    statistic = clustered_mean_test(
        inference_rows,
        bootstrap_simulations=1_000,
        permutation_draws=1_000,
    )
    return MetricComputation(
        metrics=metric_vector,
        fitness=round(fitness, 12),
        confidence_interval=statistic.confidence_interval,
        raw_brier_improvement=round(raw_brier_improvement, 12),
        candidate_calibration_error=round(candidate_calibration, 12),
        incumbent_calibration_error=round(incumbent_calibration, 12),
        candidate_compute_efficiency=round(candidate_compute_efficiency, 12),
        incumbent_compute_efficiency=round(incumbent_compute_efficiency, 12),
        abstention_rate=round(abstention_rate, 12),
        contested_count=len(contested),
    )


__all__ = ["MetricComputation", "compute_metrics"]
