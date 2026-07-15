"""Run every Phase 5 shadow guard over one frozen organism context."""

from __future__ import annotations

from .authority_guard import review_authority
from .confidence_guard import review_confidence
from .context import GuardContext
from .duplication_guard import review_duplication
from .leakage_guard import review_leakage
from .market_prior_guard import REVIEWED_MARKET_PRIOR_FLOOR, review_market_prior
from .models import ShadowReview
from .provenance_guard import review_provenance
from .regime_guard import review_regime
from .resource_guard import review_resources


def review_context(context: GuardContext) -> ShadowReview:
    return ShadowReview(
        findings=(
            review_provenance(context),
            review_leakage(context),
            review_confidence(context),
            review_duplication(context),
            review_resources(context),
            review_market_prior(context),
            review_regime(context),
            review_authority(context),
        ),
        market_prior_floor=REVIEWED_MARKET_PRIOR_FLOOR,
    )
