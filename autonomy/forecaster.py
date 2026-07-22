"""Calibration-weighted ensemble forecaster.

Fuses per-source signals by inverse-variance weighting scaled by each
source's ledger trust weight. A source only gains influence by having been
right, in this vertical, in the past — the mechanical heart of "self-
learning".
"""
from __future__ import annotations

import math
from typing import Any

from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Forecast, MarketView, Signal, Vertical
from autonomy.target_policy import is_prediction_quarantined_target

MARKET_PRIOR_MIN_SHARE = 0.05
CRYPTO_MARKET_PRIOR_MIN_SHARE = 0.25

# Inverse-variance fusion scaled by trust can drive the fused uncertainty to a
# tiny floor even when every input honors its own uncertainty floor: a
# high-trust source contributes an enormous precision weight, and correlated
# members of the same evidence family agree, so the disagreement term cannot
# arrest the collapse. Crypto short-horizon direction is where this bit hardest
# (witnessed maker fills settled net negative at a claimed ~2% uncertainty), so
# the fused crypto uncertainty is floored at the same 8% the per-signal crypto
# models use. Other verticals keep the original 2% floor.
GLOBAL_FUSED_UNCERTAINTY_FLOOR = 0.02
CRYPTO_FUSED_UNCERTAINTY_FLOOR = 0.08

# Sources in one family are alternative transforms of the same underlying
# evidence. Their family precision is the strongest member, not the sum; this
# prevents duplicate models from manufacturing certainty.
SOURCE_FAMILIES = {
    "crypto_spot_vol": "crypto_coinbase_distribution",
    "crypto_ewma_t": "crypto_coinbase_distribution",
    # Alternate volatility/regime transforms of the same crypto tape are not
    # independent evidence.  If a human later promotes either challenger,
    # it must share (not add to) the incumbent distribution family's precision.
    "crypto_blend_sigma": "crypto_coinbase_distribution",
    "crypto_empirical_regime": "crypto_coinbase_distribution",
    # Macro and crypto-equity drifts are distinct feeds but both perturb the
    # same base crypto distribution as a cross-asset risk-appetite view.  Pool
    # their precision so approving both cannot manufacture certainty.
    "crypto_macro_regime": "crypto_cross_asset_drift",
    "crypto_equities_flow": "crypto_cross_asset_drift",
    # These challengers all transform the same settled-score history into a
    # team rating. Promotion may let them contribute, but agreement among the
    # transforms is not three independent observations.
    "sports_glicko": "sports_history_ratings",
    "sports_pythagorean": "sports_history_ratings",
    "sports_mov_elo": "sports_history_ratings",
    # Final-score and box-score models are a distinct evidence lane from team
    # ratings, while still sharing one capped precision budget with each other.
    "sports_four_factors": "sports_history_scoring_boxscore",
    "sports_scoring": "sports_history_scoring_boxscore",
    # EPA/play data remains meaningfully independent of the rating and scoring
    # lanes. Naming the family explicitly keeps calibrated variants in it.
    "sports_epa": "sports_history_epa",
}


class EnsembleForecaster:
    def __init__(
        self,
        ledger: AutonomyLedger,
        promotion: Any = None,
        negative_scopes: frozenset[str] | None = None,
    ):
        self.ledger = ledger
        # Promotion registry (WS-14). Default loads the standard governance
        # files; missing files => nobody promoted => this filter is unchanged
        # (byte-identical to a build without promotion). A promoted scope is
        # the ONE way a challenger_only signal enters the live ensemble.
        if promotion is None:
            from autonomy.promotion import PromotionRegistry

            promotion = PromotionRegistry()
        self.promotion = promotion
        # Wave-19 fusion floor: scopes the settled evidence grades
        # SIGNIFICANTLY NEGATIVE (cluster-edge CI95 upper < 0) are excluded
        # from fusion entirely -- a contributor measurably worse than the
        # market on a scope must not move the fused probability there. The
        # source keeps EMITTING (challenger grading continues, so a scope
        # that recovers exits the map on evidence), and market_prior is
        # exempt (the anchor is the benchmark, never a suppressible view).
        # Fail-open: no/stale artifact -> empty set -> byte-identical fusion.
        if negative_scopes is None:
            from autonomy.no_edge_map import load_negative_scopes

            negative_scopes = load_negative_scopes()
        self._negative_scopes = negative_scopes

    def _floor_excluded(self, signal: Signal, market: MarketView) -> bool:
        if not self._negative_scopes or signal.source == "market_prior":
            return False
        from autonomy.taxonomy import grading_scope

        scope = grading_scope(signal.source, market.ticker, signal.features or {})
        return scope in self._negative_scopes

    def fuse(self, market: MarketView, signals: list[Signal]) -> Forecast | None:
        if is_prediction_quarantined_target(
            market.ticker,
            category=(market.raw or {}).get("category"),
            vertical=market.vertical,
        ):
            return None
        active_signals = [
            signal for signal in signals
            if (
                # Model observations are governed by the dedicated exact-scope
                # authority dossier, not the generic strategy-promotion file.
                # No autonomy Signal currently carries an authorized dossier
                # weight, so these rows remain gradeable but cannot enter an
                # executable ensemble through a hand-written promotion row.
                not str((signal.features or {}).get("llm_probability_authority", "")).startswith(
                    ("quarantined_", "zero_")
                )
            )
            and (not bool((signal.features or {}).get("challenger_only"))
                 or self.promotion.is_promoted_signal(
                     signal.source, market.ticker, signal.features or {}))
            and not self._floor_excluded(signal, market)
        ]
        if not active_signals:
            return None
        weighted: dict[str, float] = {}
        for signal in active_signals:
            # Exact (source, market type, horizon/phase) trust when earned;
            # vertical then global trust remain sparse-scope fallbacks.
            exact = getattr(self.ledger, "get_weight_for_signal", None)
            scoped = getattr(self.ledger, "get_weight_scoped", None)
            if callable(exact):
                trust = exact(
                    signal.source,
                    market.vertical.value,
                    market.ticker,
                    signal.features or {},
                )
            elif callable(scoped):
                trust = scoped(signal.source, market.vertical.value)
            else:
                trust = self.ledger.get_weight(signal.source, default=1.0)
            # Stage-aware probation cap (autonomous thresholded promotion): a
            # challenger promoted at STAGE 1 fuses at a fraction of its earned
            # trust until it escalates to STAGE 2 on realized-trade evidence. A
            # champion (never challenger_only) and a legacy full-weight
            # promotion both scale by 1.0, so this is byte-identical for every
            # pre-ladder path. Registries without the method (test doubles)
            # also default to 1.0.
            if bool((signal.features or {}).get("challenger_only")):
                multiplier_fn = getattr(
                    self.promotion, "weight_multiplier_for_signal", None)
                if callable(multiplier_fn):
                    trust = trust * float(multiplier_fn(
                        signal.source, market.ticker, signal.features or {}))
            variance = max(1e-4, signal.uncertainty**2)
            weight = trust / variance
            weighted[signal.source] = weight
        families: dict[str, list[Signal]] = {}
        for signal in active_signals:
            # A calibrated challenger ("{source}::cal", WS-18) is a monotone
            # transform of its parent, not independent evidence: it shares the
            # parent's family so a promoted ::cal can never double-count with
            # the parent it recalibrates. Byte-identical for non-::cal sources.
            base = signal.source[:-5] if signal.source.endswith("::cal") else signal.source
            families.setdefault(SOURCE_FAMILIES.get(base, base), []).append(signal)
        family_weights: dict[str, float] = {}
        within_family: dict[str, dict[str, float]] = {}
        for family, members in families.items():
            member_total = sum(weighted[signal.source] for signal in members)
            if member_total <= 0:
                continue
            within_family[family] = {
                signal.source: weighted[signal.source] / member_total for signal in members
            }
            family_weights[family] = max(weighted[signal.source] for signal in members)
        denominator = sum(family_weights.values())
        if denominator <= 0:
            return None
        normalized_raw: dict[str, float] = {}
        for family, family_weight in family_weights.items():
            family_share = family_weight / denominator
            for source, member_share in within_family[family].items():
                normalized_raw[source] = family_share * member_share
        probabilities = {signal.source: signal.probability_yes for signal in active_signals}
        normalized = dict(normalized_raw)
        prior_share = normalized.get("market_prior", 0.0)
        prior_floor = (
            CRYPTO_MARKET_PRIOR_MIN_SHARE
            if market.vertical is Vertical.CRYPTO
            else MARKET_PRIOR_MIN_SHARE
        )
        if 0.0 < prior_share < prior_floor and len(normalized) > 1:
            other_total = 1.0 - prior_share
            for source in normalized:
                if source != "market_prior":
                    normalized[source] = (
                        normalized[source] / other_total * (1.0 - prior_floor)
                    )
            normalized["market_prior"] = prior_floor
        probability = min(0.995, max(0.005, sum(
            normalized[source] * probabilities[source] for source in normalized
        )))
        # Effective-family precision handles duplicate data; model disagreement
        # prevents a polarized ensemble from claiming tiny uncertainty.
        inverse_precision = (1.0 / denominator) ** 0.5
        disagreement = math.sqrt(sum(
            normalized[source] * (probabilities[source] - probability) ** 2
            for source in normalized
        ))
        sigma_floor = (
            CRYPTO_FUSED_UNCERTAINTY_FLOOR
            if market.vertical is Vertical.CRYPTO
            else GLOBAL_FUSED_UNCERTAINTY_FLOOR
        )
        fused_sigma = min(0.5, max(sigma_floor, inverse_precision, disagreement))

        # Honest-quote gate (Wave-5): a dead/wide book yields NO implied
        # probability rather than a fabricated ~50c mid. Downstream this means
        # no claimed edge, no decision benchmark, and no adverse-selection
        # phantom on markets nobody is actually quoting.
        from autonomy.quote_quality import honest_implied_yes

        implied = honest_implied_yes(market.yes_bid, market.yes_ask)
        edge = probability - implied if implied is not None else 0.0

        normalized = {source: round(share, 4) for source, share in normalized.items()}
        rationale = "; ".join(
            f"{s.source}:{s.probability_yes:.2f}±{s.uncertainty:.2f}" for s in active_signals
        )
        return Forecast(
            market_ticker=market.ticker,
            probability_yes=probability,
            uncertainty=fused_sigma,
            sources_used=normalized,
            market_implied_yes=implied,
            edge_yes=edge,
            rationale=rationale[:600],
        )
