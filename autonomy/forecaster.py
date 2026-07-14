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
}


class EnsembleForecaster:
    def __init__(self, ledger: AutonomyLedger, promotion: Any = None):
        self.ledger = ledger
        # Promotion registry (WS-14). Default loads the standard governance
        # files; missing files => nobody promoted => this filter is unchanged
        # (byte-identical to a build without promotion). A promoted scope is
        # the ONE way a challenger_only signal enters the live ensemble.
        if promotion is None:
            from autonomy.promotion import PromotionRegistry

            promotion = PromotionRegistry()
        self.promotion = promotion

    def fuse(self, market: MarketView, signals: list[Signal]) -> Forecast | None:
        active_signals = [
            signal for signal in signals
            if not bool((signal.features or {}).get("challenger_only"))
            or self.promotion.is_promoted_signal(
                signal.source, market.ticker, signal.features or {})
        ]
        if not active_signals:
            return None
        weighted: dict[str, float] = {}
        for signal in active_signals:
            # Vertical-scoped trust when the ledger has earned one; a source's
            # authority is domain-specific, not global. Duck-typed fallback
            # keeps minimal ledger stand-ins working.
            scoped = getattr(self.ledger, "get_weight_scoped", None)
            if callable(scoped):
                trust = scoped(signal.source, market.vertical.value)
            else:
                trust = self.ledger.get_weight(signal.source, default=1.0)
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

        implied = None
        if market.yes_bid is not None and market.yes_ask is not None and market.yes_ask > 0:
            implied = ((market.yes_bid + market.yes_ask) / 2.0) / 100.0
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
