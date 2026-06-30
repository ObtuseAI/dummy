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
]
