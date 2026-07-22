from strategies.probability_disagreement import ProbabilityDisagreement
from strategies.spread_capture import SpreadCapture
from strategies.market_making import MarketMaking
from strategies.mean_reversion import MeanReversion
from strategies.momentum import Momentum
from strategies.settlement_mispricing import SettlementMispricing
from strategies.liquidity_dislocation import LiquidityDislocation
from strategies.cross_market_arbitrage import CrossMarketArbitrage
from strategies.news_latency import NewsLatency
from strategies.orderbook_pressure import OrderbookPressure
from strategies.closing_time_pressure import ClosingTimePressure
from strategies.stale_quote_detection import StaleQuoteDetection
from strategies.event_cluster_hedging import EventClusterHedging
from strategies.correlated_contract_arbitrage import CorrelatedContractArbitrage
from strategies.volume_dislocation import VolumeDislocation
from strategies.implied_probability_reversion import ImpliedProbabilityReversion
from strategies.repo_derived import (
    SportsMomentumStrategy,
    CryptoEventMarketStrategy,
    RepoDerivedCrossMarketArbitrage,
    OrderbookSpreadCaptureStrategy,
    StaleQuoteDetectionStrategy,
)

REPO_DERIVED_STRATEGIES = [
    SportsMomentumStrategy(),
    CryptoEventMarketStrategy(),
    RepoDerivedCrossMarketArbitrage(),
    OrderbookSpreadCaptureStrategy(),
    StaleQuoteDetectionStrategy(),
]


def has_prediction_authority(strategy: object) -> bool:
    """Return whether a strategy may be evaluated for a trade proposal.

    Authority must be explicit (including an inherited declaration from
    ``StrategyGenome``).  An injected duck-typed strategy with no declaration
    is unknown authority and therefore inactive.
    """
    return (
        not bool(getattr(strategy, "DATA_ONLY", False))
        and getattr(strategy, "PREDICTION_AUTHORITY", None) is True
    )


ACTIVE_REPO_DERIVED_FAMILY_NAMES = tuple(
    strategy.name
    for strategy in REPO_DERIVED_STRATEGIES
    if has_prediction_authority(strategy)
)
ACTIVE_REPO_DERIVED_FAMILY_COUNT = len(ACTIVE_REPO_DERIVED_FAMILY_NAMES)

STRATEGIES = [
    ProbabilityDisagreement(),
    SpreadCapture(),
    MarketMaking(),
    MeanReversion(),
    Momentum(),
    SettlementMispricing(),
    LiquidityDislocation(),
    CrossMarketArbitrage(),
    NewsLatency(),
    OrderbookPressure(),
    ClosingTimePressure(),
    StaleQuoteDetection(),
    EventClusterHedging(),
    CorrelatedContractArbitrage(),
    VolumeDislocation(),
    ImpliedProbabilityReversion(),
    *[
        strategy
        for strategy in REPO_DERIVED_STRATEGIES
        if has_prediction_authority(strategy)
    ],
]


def get_repo_derived_strategies() -> list:
    """Return active repo-derived strategies (data-only targets excluded)."""
    return [
        strategy
        for strategy in REPO_DERIVED_STRATEGIES
        if has_prediction_authority(strategy)
    ]
