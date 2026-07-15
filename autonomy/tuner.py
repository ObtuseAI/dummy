"""Propose-then-promote parameter tuner (WS-9, spec section 3.4).

Challenger-only, artifact-only: this module PROPOSES better sigma/edge
scalars for the sports engines in one JSON artifact
(``runtime/autonomy/tuning_proposals.json``) and NEVER writes a constant
back into any ``.py`` file. Promotion is an explicit, human-reviewed
governance action -- a person reads the artifact and edits the constant in a
PR citing it, exactly like the strategy miner's rule proposals (WS-1c)
already work. The single non-negotiable safety property is that source-file
hashes are byte-identical before and after a full tuner run (see
``tests/test_autonomy_tuner.py``'s no-mutation test).

Discipline mirrors ``autonomy/strategy_miner.py`` exactly:
  * Walk-forward honesty: the winning grid value is picked on TRAIN only,
    then evaluated ONCE, out-of-sample, on TEST (``_purged_split`` --
    reused directly from the miner, not re-implemented).
  * Per-event-cluster means, never per-row: emissions that share a
    settlement print (winner/spread/total for the same game) are
    correlated, so both the training objective and the test CI are computed
    over one mean-Brier-per-cluster, never raw per-row values.
  * Family-size disclosure: the artifact's top-level block states how many
    tunables were evaluated and how many total grid points were tried
    across all of them, so a reader can judge the multiple-comparisons
    exposure the same way the miner's ``rules_tested`` field does.
  * Honest skips: a tunable whose settled rows don't carry the feature
    inputs needed to reprice it (or whose real production code path never
    actually uses the constant under test -- see NHL below) is marked
    ``not_repriceable`` and the reason is recorded, never silently dropped
    or fabricated.

TUNABLE REGISTRY -- what's in, what's out, and why
----------------------------------------------------
Every ``current`` value below is IMPORTED from the real engine constant
(never hand-copied), so the registry cannot drift from source:

  * ``nba_total_sigma_base`` / ``nba_margin_sigma_base`` --
    ``autonomy.sports.nba_model.NBA_PARAMS`` (the pace x efficiency
    engine). Repriceable via the engine's own pure
    ``total_over_probability`` / ``spread_cover_probability`` helpers,
    pace-scaled exactly like ``heteroskedastic_sigmas`` does.
  * ``ncaamb_total_sigma_base`` / ``ncaamb_margin_sigma_base`` --
    ``autonomy.sports.college.NCAAMB_PARAMS`` (same ``NbaModel`` engine,
    NCAAMB's own pace reference/priors). Same repricing path as NBA.
  * ``nfl_total_sigma`` -- ``autonomy.sports.team_scores.
    LEAGUE_SCORE_CONFIGS["nfl"].total_sigma``. NOT
    ``NflMarginModel.TOTAL_SIGMA`` (13.5): a read of
    ``autonomy/signals/sports_intelligence.py``'s ``total`` market branch
    shows NFL is never routed through ``NflMarginModel.total_over_
    probability`` at all -- NFL totals fall through to the generic
    ``TeamScoreModel`` path unconditionally, so ``NflMarginModel.
    TOTAL_SIGMA`` is dead code for pricing purposes and tuning it would
    propose a fix for a constant nothing reads. This is exactly the kind of
    thing walk-forward-on-real-rows catches that reading the class
    docstring wouldn't.
  * ``ncaaf_total_sigma`` -- ``LEAGUE_SCORE_CONFIGS["ncaaf"].total_sigma``,
    the constant ``autonomy.sports.college.ncaaf_college`` actually threads
    into ``NcaafCollegeModel``.
  * NFL/NCAAF |margin| PMFs are FIXED per the brief -- no PMF entries here,
    only the total-sigma scalars above.
  * ``nhl_home_edge`` -- ``autonomy.sports.nhl_model.HOME_EDGE``, listed
    for completeness (every engine gets an entry) but ALWAYS verdict
    ``not_repriceable``: NHL prices off a bivariate-Poisson goal matrix,
    not a normal(mean, sigma) pair, so there is no honest way to reprice a
    settled NHL row under a candidate constant using only the normal-CDF
    helpers this tuner is scoped to reuse (the brief is explicit: reuse
    existing pure helpers, never reimplement distributional math). Fitting
    NHL's Poisson kernel is a real future workstream, not something to fake
    here with a normal approximation.
  * MLB is out of scope entirely: its run-scoring model
    (``autonomy/sports/mlb_pa_sim.py``) is a play-by-play simulation with no
    single scalar sigma/edge constant comparable to the ones above.
  * Trading-decision "edge floor" constants (``autonomy/mispricing.py``,
    ``autonomy/promotion.py``, ``autonomy/risk_brain.py``) are excluded on
    purpose: they gate WHETHER to trade, they don't change what
    ``probability_yes`` a settled row carries, so there is nothing for a
    Brier-calibration objective to fit them against. A PnL/Sharpe backtest
    would be the honest tool for those, which is a different workstream.

SUBJECT-SIDE INFERENCE FOR MARGIN TUNABLES
-------------------------------------------
``MinedRow`` doesn't carry an explicit "which side is the subject" field.
Margin/spread repricing needs to know whether ``probability_yes`` prices the
home or away team. Rather than fabricate this, ``_subject_is_home`` reads it
straight off the market ticker using the EXACT convention already shipped in
``autonomy/signals/sports_elo.py::parse_game_ticker`` (winner tickers:
``parts[2]`` is the bare subject abbreviation) and
``autonomy/signals/sports_intelligence.py::parse_sports_contract`` (spread
tickers: ``parts[2]`` is ``"<SUBJECT><strike-index>"``, e.g. ``"KC3"``, so
the trailing digits are stripped with the same regex used there). A ticker
that doesn't parse into either shape, or whose extracted subject matches
neither ``features["home"]`` nor ``features["away"]``, is excluded from that
row's repricing (fail-closed per row, never guessed).
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from autonomy.sports import nba_model, team_scores
from autonomy.sports.college import NCAAMB_PARAMS
from autonomy.sports.nhl_model import HOME_EDGE as NHL_HOME_EDGE
from autonomy.stats import mean_ci95
from autonomy.strategy_miner import MinedRow, _purged_split, load_settled_rows

# The interface note this task was briefed from names a `MIN_CLUSTERS`
# constant on autonomy/strategy_miner.py; the module that actually merged
# defines `MIN_TEST_CLUSTERS` (same purpose -- minimum event clusters for an
# out-of-sample verdict). Imported under the briefed name so the intent
# ("respect it") is honored without inventing a second, possibly-divergent
# threshold; see the WS-9 report for this discrepancy on record.
from autonomy.strategy_miner import MIN_TEST_CLUSTERS as MIN_CLUSTERS

# WS-B loop wiring: the loss-deconstruction evolution engine's priority read.
# ORDER/ANNOTATE ONLY -- see _load_loss_priority and its use in
# tuning_report(). Never touches _fit_tunable or the walk-forward CI gate.
DEFAULT_LOSS_ATTRIBUTION_PATH = Path("runtime/autonomy/loss_attribution.json")

# -- subject-side inference (see module docstring) --------------------------
_SPREAD_SUBJECT_RE = re.compile(r"^([A-Z]+)\d+$")


def _subject_is_home(ticker: str, home: Any, away: Any) -> bool | None:
    parts = str(ticker).upper().split("-")
    if len(parts) < 3:
        return None
    tail = parts[2]
    match = _SPREAD_SUBJECT_RE.match(tail)
    subject = match.group(1) if match else tail
    home_u = str(home or "").upper()
    away_u = str(away or "").upper()
    if not home_u or not away_u:
        return None
    if subject == home_u:
        return True
    if subject == away_u:
        return False
    return None


# -- repricing helpers --------------------------------------------------------
# Every function here reuses an existing pure helper for the actual
# probability math (nba_model's/team_scores' normal-CDF-based functions) --
# none of them reimplement a CDF; they only compute the sigma/margin inputs
# those functions take.


def _reprice_total_normal(
    row: MinedRow, candidate: float, *, pace_reference: float | None,
) -> float | None:
    """Shared TOTAL repricer for the two PaceParams engines (NBA/NCAAMB).

    ``pace_reference`` scales the candidate base sigma by the same
    sqrt(expected_pace / reference) ratio the real engine applies (see
    ``nba_model.heteroskedastic_sigmas``) -- reusing the identical formula,
    not reimplementing it, since it's simple arithmetic feeding into the
    reused normal helper, not a CDF.
    """
    features = row.features
    expected_total = features.get("expected_total")
    threshold = features.get("threshold")
    if expected_total is None or threshold is None:
        return None
    if pace_reference is not None:
        expected_pace = features.get("expected_pace")
        if expected_pace is None:
            return None
        ratio = math.sqrt(max(0.0, float(expected_pace)) / pace_reference)
        sigma = float(candidate) * ratio
    else:
        sigma = float(candidate)
    return nba_model.total_over_probability(float(expected_total), sigma, float(threshold))


def _reprice_margin_normal(
    row: MinedRow, candidate: float, *, pace_reference: float | None,
) -> float | None:
    """Shared SPREAD/WINNER repricer for the two PaceParams engines.

    WINNER rows carry no ``threshold`` feature (only spread/total contracts
    set one) -- 0.0 is used, which is exactly what
    ``nba_model.spread_cover_probability`` reduces to
    ``win_probability_from_margin`` at (see that function's own docstring).
    """
    features = row.features
    home_score = features.get("expected_home_score")
    away_score = features.get("expected_away_score")
    if home_score is None or away_score is None:
        return None
    subject_home = _subject_is_home(row.ticker, features.get("home"), features.get("away"))
    if subject_home is None:
        return None
    market_type = features.get("market_type")
    if market_type == "spread":
        threshold = features.get("threshold")
        if threshold is None:
            return None
        threshold = float(threshold)
    elif market_type == "winner":
        threshold = 0.0
    else:
        return None
    home_margin = float(home_score) - float(away_score)
    subject_margin = home_margin if subject_home else -home_margin
    if pace_reference is not None:
        expected_pace = features.get("expected_pace")
        if expected_pace is None:
            return None
        ratio = math.sqrt(max(0.0, float(expected_pace)) / pace_reference)
        sigma = float(candidate) * ratio
    else:
        sigma = float(candidate)
    return nba_model.spread_cover_probability(subject_margin, sigma, threshold)


def _reprice_team_scores_total(row: MinedRow, candidate: float) -> float | None:
    """NFL/NCAAF TOTAL repricer -- the generic ``TeamScoreModel`` normal,
    the constant real production code actually reads for these two totals
    (see the module docstring's NFL discrepancy note)."""
    features = row.features
    expected_total = features.get("expected_total")
    threshold = features.get("threshold")
    if expected_total is None or threshold is None:
        return None
    return team_scores.normal_over_probability(float(expected_total), float(candidate), float(threshold))


def _not_repriceable(row: MinedRow, candidate: float) -> float | None:  # noqa: ARG001
    return None


# -- registry -----------------------------------------------------------------


@dataclass(frozen=True)
class _TunableSpec:
    name: str
    current: float
    grid: tuple[float, ...]
    applies_to: str
    market_type: str
    market_types: tuple[str, ...]
    reprice: Callable[[MinedRow, float], float | None]
    model_version_key: str | None = None
    model_version_value: str | None = None
    skip_reason: str | None = None

    def matches(self, row: MinedRow) -> bool:
        features = row.features
        if features.get("sport") != self.applies_to:
            return False
        if features.get("market_type") not in self.market_types:
            return False
        if self.model_version_key is not None:
            if features.get(self.model_version_key) != self.model_version_value:
                return False
        return True


def _spec(
    name: str, current: float, grid: list[float], applies_to: str, market_type: str,
    market_types: tuple[str, ...], reprice: Callable[[MinedRow, float], float | None],
    *, model_version_key: str | None = None, model_version_value: str | None = None,
    skip_reason: str | None = None,
) -> _TunableSpec:
    return _TunableSpec(
        name=name, current=float(current), grid=tuple(float(g) for g in grid),
        applies_to=applies_to, market_type=market_type, market_types=market_types,
        reprice=reprice, model_version_key=model_version_key,
        model_version_value=model_version_value, skip_reason=skip_reason,
    )


def _sigma_grid(current: float) -> list[float]:
    """±2 in 1.0 steps around the current constant (the brief's own worked
    example: 19.5 -> [17.5, 18.5, 19.5, 20.5, 21.5])."""
    return [round(current + step, 4) for step in (-2.0, -1.0, 0.0, 1.0, 2.0)]


_SPECS: list[_TunableSpec] = [
    _spec(
        "nba_total_sigma_base", nba_model.NBA_PARAMS.total_sigma_base,
        _sigma_grid(nba_model.NBA_PARAMS.total_sigma_base), "nba", "total", ("total",),
        lambda row, candidate: _reprice_total_normal(
            row, candidate, pace_reference=nba_model.NBA_PARAMS.sigma_pace_reference),
        model_version_key="margin_model_version", model_version_value=nba_model.MODEL_VERSION,
    ),
    _spec(
        "nba_margin_sigma_base", nba_model.NBA_PARAMS.margin_sigma_base,
        _sigma_grid(nba_model.NBA_PARAMS.margin_sigma_base), "nba", "spread+winner",
        ("spread", "winner"),
        lambda row, candidate: _reprice_margin_normal(
            row, candidate, pace_reference=nba_model.NBA_PARAMS.sigma_pace_reference),
        model_version_key="margin_model_version", model_version_value=nba_model.MODEL_VERSION,
    ),
    _spec(
        "ncaamb_total_sigma_base", NCAAMB_PARAMS.total_sigma_base,
        _sigma_grid(NCAAMB_PARAMS.total_sigma_base), "ncaamb", "total", ("total",),
        lambda row, candidate: _reprice_total_normal(
            row, candidate, pace_reference=NCAAMB_PARAMS.sigma_pace_reference),
        model_version_key="margin_model_version", model_version_value=NCAAMB_PARAMS.version,
    ),
    _spec(
        "ncaamb_margin_sigma_base", NCAAMB_PARAMS.margin_sigma_base,
        _sigma_grid(NCAAMB_PARAMS.margin_sigma_base), "ncaamb", "spread+winner",
        ("spread", "winner"),
        lambda row, candidate: _reprice_margin_normal(
            row, candidate, pace_reference=NCAAMB_PARAMS.sigma_pace_reference),
        model_version_key="margin_model_version", model_version_value=NCAAMB_PARAMS.version,
    ),
    _spec(
        "nfl_total_sigma", team_scores.LEAGUE_SCORE_CONFIGS["nfl"].total_sigma,
        _sigma_grid(team_scores.LEAGUE_SCORE_CONFIGS["nfl"].total_sigma), "nfl", "total", ("total",),
        _reprice_team_scores_total,
    ),
    _spec(
        "ncaaf_total_sigma", team_scores.LEAGUE_SCORE_CONFIGS["ncaaf"].total_sigma,
        _sigma_grid(team_scores.LEAGUE_SCORE_CONFIGS["ncaaf"].total_sigma), "ncaaf", "total", ("total",),
        _reprice_team_scores_total,
    ),
    _spec(
        "nhl_home_edge", NHL_HOME_EDGE,
        [round(NHL_HOME_EDGE + step, 4) for step in (-0.10, -0.05, 0.0, 0.05, 0.10)],
        "nhl", "winner", ("winner", "spread", "total"),
        _not_repriceable,
        skip_reason=(
            "NHL prices off a bivariate-Poisson goal matrix (autonomy/sports/"
            "nhl_model.py), not a normal(mean, sigma) pair -- there is no honest"
            " reprice of a settled row under a candidate HOME_EDGE using only the"
            " normal-CDF helpers this tuner reuses. Fitting the Poisson kernel is"
            " a future workstream, not faked here with a normal approximation."
        ),
    ),
]

# Public, JSON-safe registry exactly matching the brief's schema -- every
# `current` is read straight off `_SPECS`, which itself imported each value
# from the real engine constant above, so this list can't drift from source.
TUNABLES: list[dict[str, Any]] = [
    {
        "name": spec.name, "current": spec.current, "grid": list(spec.grid),
        "applies_to": spec.applies_to, "market_type": spec.market_type,
    }
    for spec in _SPECS
]


# -- fit loop -------------------------------------------------------------


def _cluster_means(rows: list[MinedRow], score: Callable[[MinedRow], float | None]) -> list[float]:
    """One mean score per event cluster (mirrors strategy_miner.py's
    ``_cluster_mean_edges`` -- same correlated-emissions rationale, but
    generalized over an arbitrary per-row score function instead of the
    miner's fixed market-edge score)."""
    sums: dict[str, list[float]] = {}
    for row in rows:
        value = score(row)
        if value is None:
            continue
        sums.setdefault(row.event_cluster, []).append(value)
    return [sum(values) / len(values) for values in sums.values()]


def _brier(probability: float, outcome: bool) -> float:
    target = 1.0 if outcome else 0.0
    return (probability - target) ** 2


def _fit_tunable(spec: _TunableSpec, rows: list[MinedRow]) -> dict[str, Any]:
    base: dict[str, Any] = {
        "name": spec.name, "applies_to": spec.applies_to, "market_type": spec.market_type,
        "current": spec.current, "best": spec.current, "train_delta": 0.0,
        "test_delta": 0.0, "test_ci95": [None, None], "n_clusters": 0, "verdict": "keep",
    }
    if spec.skip_reason is not None:
        base["verdict"] = "not_repriceable"
        base["reason"] = spec.skip_reason
        return base

    filtered = [row for row in rows if spec.matches(row)]
    filtered_clusters = {row.event_cluster for row in filtered}
    if len(filtered_clusters) < MIN_CLUSTERS:
        base["n_clusters"] = len(filtered_clusters)
        base["verdict"] = "insufficient_data"
        return base

    usable = [row for row in filtered if spec.reprice(row, spec.current) is not None]
    if not usable:
        base["verdict"] = "not_repriceable"
        base["reason"] = "no settled row carried the feature inputs needed to reprice this tunable"
        return base

    usable_clusters = {row.event_cluster for row in usable}
    if len(usable_clusters) < MIN_CLUSTERS:
        base["n_clusters"] = len(usable_clusters)
        base["verdict"] = "insufficient_data"
        return base

    train, test = _purged_split(usable)
    if not train or not test:
        base["n_clusters"] = len(usable_clusters)
        base["verdict"] = "insufficient_data"
        return base

    def _train_score(candidate: float) -> Callable[[MinedRow], float | None]:
        def _score(row: MinedRow) -> float | None:
            probability = spec.reprice(row, candidate)
            if probability is None:
                return None
            return _brier(probability, row.result_yes)
        return _score

    train_clusters_for = {
        candidate: _cluster_means(train, _train_score(candidate)) for candidate in spec.grid
    }
    train_means = {
        candidate: (sum(values) / len(values) if values else float("inf"))
        for candidate, values in train_clusters_for.items()
    }
    best = min(spec.grid, key=lambda candidate: train_means[candidate])
    current_train_clusters = train_clusters_for.get(spec.current)
    if current_train_clusters is None:
        current_train_clusters = _cluster_means(train, _train_score(spec.current))
    current_train_mean = (
        sum(current_train_clusters) / len(current_train_clusters) if current_train_clusters else None
    )
    train_delta = (
        round(current_train_mean - train_means[best], 6)
        if current_train_mean is not None else None
    )

    # Out-of-sample exam: paired per-cluster delta (current brier - best
    # brier), so the CI is about the IMPROVEMENT, not either brier alone.
    test_current_by_cluster: dict[str, list[float]] = {}
    test_best_by_cluster: dict[str, list[float]] = {}
    for row in test:
        current_probability = spec.reprice(row, spec.current)
        best_probability = spec.reprice(row, best)
        if current_probability is None or best_probability is None:
            continue
        test_current_by_cluster.setdefault(row.event_cluster, []).append(
            _brier(current_probability, row.result_yes))
        test_best_by_cluster.setdefault(row.event_cluster, []).append(
            _brier(best_probability, row.result_yes))
    shared_clusters = sorted(set(test_current_by_cluster) & set(test_best_by_cluster))
    deltas = []
    for cluster in shared_clusters:
        current_vals = test_current_by_cluster[cluster]
        best_vals = test_best_by_cluster[cluster]
        current_mean = sum(current_vals) / len(current_vals)
        best_mean = sum(best_vals) / len(best_vals)
        deltas.append(current_mean - best_mean)

    base["best"] = best
    base["train_delta"] = train_delta if train_delta is not None else 0.0
    base["n_clusters"] = len(shared_clusters)

    if len(shared_clusters) < MIN_CLUSTERS:
        base["verdict"] = "insufficient_data"
        return base

    stats = mean_ci95(deltas)
    if stats is None or stats.get("lower") is None or stats.get("upper") is None:
        base["test_delta"] = round(stats["mean"], 6) if stats else 0.0
        base["verdict"] = "keep"
        return base

    test_delta = float(stats["mean"])
    lower = float(stats["lower"])
    upper = float(stats["upper"])
    base["test_delta"] = round(test_delta, 6)
    base["test_ci95"] = [round(lower, 6), round(upper, 6)]
    if best != spec.current and test_delta > 0.0 and lower > 0.0 and len(shared_clusters) >= MIN_CLUSTERS:
        base["verdict"] = "candidate"
    else:
        base["verdict"] = "keep"
    return base


def _load_loss_priority(path: Path | None) -> list[str]:
    """Read-only, fail-closed priority read (WS-B loop wiring).

    Missing file, corrupt JSON, or any other trouble -> empty list -> no-op
    ordering, identical to the artifact never having existed. This is the
    ONLY thing the loss-deconstruction engine is allowed to influence here:
    which order ``tuning_report`` lists tunables in, and a ``bleeding_priority``
    annotation on each proposal. It must never reach ``_fit_tunable`` or any
    field ``_fit_tunable`` computes.
    """
    target = path if path is not None else DEFAULT_LOSS_ATTRIBUTION_PATH
    try:
        if not target.exists():
            return []
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return []
    try:
        from autonomy.loss_engine import loss_priority

        return loss_priority(data)
    except Exception:
        return []


def _tunable_is_bleeding(spec: _TunableSpec, scope: str) -> bool:
    """Does an exact-cohort WS-B bleeding scope key
    describe this tunable? Matching only, never a value change."""
    parts = str(scope or "").split("|")
    if len(parts) < 3:
        return False
    specialist = parts[0]
    market_type = parts[2] if len(parts) >= 4 else parts[1]
    return specialist == spec.applies_to and market_type in spec.market_types


def tuning_report(
    conn: sqlite3.Connection, *, now_iso: str,
    loss_attribution_path: Path | None = None,
) -> dict[str, Any]:
    """One full tuning pass -> JSON-able proposal artifact.

    Read-only against the ledger; writes NOTHING but the returned dict
    (the caller decides whether/where to persist it via ``write_report``).

    ``loss_attribution_path`` (WS-B loop wiring, defaults to
    ``runtime/autonomy/loss_attribution.json``) is read fail-closed to
    decide which tunables to list FIRST and to annotate with
    ``bleeding_priority`` -- it is applied strictly AFTER every proposal's
    verdict/fields are already computed below, so it can never change a
    walk-forward CI gate or a candidate/keep verdict, only the order the
    (otherwise byte-identical) proposals are listed in.
    """
    rows = load_settled_rows(conn)
    proposals = [_fit_tunable(spec, rows) for spec in _SPECS]  # gate/verdict: UNCHANGED by priority
    total_grid_points = sum(len(spec.grid) for spec in _SPECS)

    priority_scopes = _load_loss_priority(loss_attribution_path)
    spec_by_name = {spec.name: spec for spec in _SPECS}
    for proposal in proposals:
        spec = spec_by_name[proposal["name"]]
        proposal["bleeding_priority"] = any(
            _tunable_is_bleeding(spec, scope) for scope in priority_scopes
        )
    if priority_scopes:
        # Stable sort: bleeding-priority tunables first, original registry
        # order preserved within each group. Ordering/annotation ONLY --
        # every proposal dict's content besides this new key is untouched.
        proposals.sort(key=lambda proposal: not proposal["bleeding_priority"])

    return {
        "generated_at": now_iso,
        "settled_rows": len(rows),
        "proposals": proposals,
        "loss_priority_scopes": priority_scopes,
        "candidate_count": sum(1 for proposal in proposals if proposal["verdict"] == "candidate"),
        # Multiple-comparisons disclosure (mirrors strategy_miner.py's
        # `rules_tested`/`expected_false_positives` block): how many
        # tunables were evaluated and how many total grid points were tried
        # across all of them, so a reader can judge the exposure behind any
        # "candidate" verdict above.
        "family_size": {
            "tunables_evaluated": len(_SPECS),
            "grid_points_evaluated": total_grid_points,
        },
        "note": (
            "Proposal artifact only -- NEVER writes a constant back to any .py"
            " file. Fit walk-forward on settled, market-benchmarked signal"
            " history; CIs use per-event-cluster means; promotion is an"
            " explicit human governance action (edit the constant in a PR"
            " citing this artifact)."
        ),
    }


def write_report(report: dict[str, Any], path: Path) -> None:
    """Byte-for-byte the same atomic-write pattern as
    ``strategy_miner.write_report`` (write to a temp file, then replace) --
    reused convention, not reinvented."""
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)
