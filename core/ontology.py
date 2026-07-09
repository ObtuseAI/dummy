from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class ForecastOpinion(BaseModel):
    market_ticker: str
    contract_ticker: str
    forecast_reference: str
    market_implied_probability: Decimal
    dummy_probability: Decimal
    probability_delta: Decimal
    confidence_score: Decimal
    uncertainty_band: tuple[Decimal, Decimal]
    model_summary: str
    reasoning: str
    no_trade_reason: str | None = None
    calibration_notes: list[str] = Field(default_factory=list)
    timestamp: datetime
    expiration: datetime
    proof_reference: str


class StrategyCritique(BaseModel):
    strategy_family: str
    market_ticker: str
    contract_ticker: str
    verdict: str  # "proceed", "warn", "block"
    edge_assessment: str
    risk_assessment: str
    confidence_adjustment: Decimal = Decimal("0")
    reasoning: str
    timestamp: datetime
    proof_reference: str


class NoTradeReason(BaseModel):
    market_ticker: str
    contract_ticker: str
    reason: str
    contributing_factors: list[str] = Field(default_factory=list)
    model_summary: str
    timestamp: datetime
    proof_reference: str


class TradeProposalDraft(BaseModel):
    market_ticker: str
    contract_ticker: str
    side: str
    price_cents: int
    size: int
    reasoning: str
    timestamp: datetime


class HybridReviewResult(BaseModel):
    task: str
    primary: dict
    secondary: dict
    agreement_score: Decimal
    confidence_adjustment: Decimal
    verdict: str
    reasoning: str
    timestamp: datetime
    proof_reference: str


class CalibrationNote(BaseModel):
    market_ticker: str
    contract_ticker: str
    note: str
    source: str
    timestamp: datetime


class MarketThesis(BaseModel):
    market_ticker: str
    contract_ticker: str
    thesis: str
    bullish_signals: list[str] = Field(default_factory=list)
    bearish_signals: list[str] = Field(default_factory=list)
    source: str
    timestamp: datetime


class AccountMode(str, Enum):
    OFF = "OFF"
    READ_ONLY = "READ_ONLY"
    AUTONOMOUS_LIVE_CAPPED = "AUTONOMOUS_LIVE_CAPPED"
    EMERGENCY_STOP = "EMERGENCY_STOP"

class OrderBookLevel(BaseModel):
    price: int
    size: int

class OrderBook(BaseModel):
    market_ticker: str
    contract_ticker: str
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]
    timestamp: datetime
    source_ts: Optional[datetime] = None
    freshness_score: Optional[Decimal] = None
    depth_summary: Optional[dict[str, Any]] = None

class ProbabilityEstimate(BaseModel):
    value: Decimal = Field(..., ge=0, le=1)
    uncertainty_band: tuple[Decimal, Decimal]
    source_summary: str

class EdgeEstimate(BaseModel):
    expected_edge_bps: int
    edge_after_fees_bps: int
    confidence_score: Decimal = Field(..., ge=0, le=1)

class Forecast(BaseModel):
    market_ticker: str
    contract_ticker: str
    event_title: str
    contract_title: str
    market_implied_probability: Decimal
    dummy_probability: Decimal
    probability_delta: Decimal
    confidence_score: Decimal
    uncertainty_band: tuple[Decimal, Decimal]
    expected_edge: Decimal
    edge_after_fees: Decimal
    freshness_score: Decimal
    liquidity_score: Decimal
    spread_score: Decimal
    orderbook_depth_score: Decimal
    settlement_risk_score: Decimal
    source_summary: str
    model_summary: str
    calibration_notes: str
    timestamp: datetime
    expiration: datetime
    strategy_references: list[str]
    proof_reference: str

class TradeProposal(BaseModel):
    id: str
    market_ticker: str
    contract_ticker: str
    side: str
    price_cents: int
    size: int
    forecast_reference: str
    edge_estimate: EdgeEstimate
    risk_estimate: str
    confidence_estimate: Decimal
    expected_fill_behavior: str
    stop_condition: str
    cancellation_condition: str
    cap_impact: dict[str, Any]
    compliance_verdict: "ComplianceVerdict"
    proof_reference: str

class ComplianceVerdict(BaseModel):
    passed: bool
    blocked_categories: list[str]
    reason: str

class RiskVerdict(BaseModel):
    passed: bool
    reason: str
    metrics: dict[str, Any]

class FirewallVerdict(BaseModel):
    allow: bool
    reason: str
    rejected_by: Optional[str] = None

class LiveOrderRequest(BaseModel):
    proposal_id: str
    market_ticker: str
    contract_ticker: str
    side: str
    price_cents: int
    size: int
    strategy_proof_reference: str
    forecast_proof_reference: str
    adapter_name: str

class LiveOrderResult(BaseModel):
    success: bool
    order_id: Optional[str] = None
    error: Optional[str] = None
    proof_reference: str
    # Structured broker-rejection diagnostics (safe, non-secret)
    broker_rejection_code: Optional[str] = None
    broker_rejection_safe_message: Optional[str] = None
    broker_rejection_http_status: Optional[int] = None
    broker_rejection_adapter_error_type: Optional[str] = None
    broker_rejection_stage: Optional[str] = None
    broker_rejection_raw_redacted: Optional[dict[str, Any]] = None

class CancelRequest(BaseModel):
    order_id: str
    market_ticker: str
    reason: str

class CapConfig(BaseModel):
    max_single_order_cents: int = 100
    max_market_exposure_cents: int = 500
    max_daily_loss_cents: int = 500
    max_total_live_exposure_cents: int = 1000
    max_open_markets: int = 3
    max_orders_per_hour: int = 5
    allow_market_orders: bool = False
    limit_orders_only: bool = True
    auto_cancel_stale_orders: bool = True
    kill_switch_required: bool = True
    allowed_markets: list[str] = []
    blocked_categories: list[str] = []
    max_spread_cents: int = 5
    min_liquidity: int = 10
    min_edge_bps: int = 50

class KillSwitchState(BaseModel):
    active: bool
    triggered_at: Optional[datetime] = None
    reason: Optional[str] = None

class EmergencyStopState(BaseModel):
    active: bool
    triggered_at: Optional[datetime] = None
    cancel_open_orders: bool = True

class Position(BaseModel):
    market_ticker: str
    contract_ticker: str
    side: str
    quantity: int
    avg_price_cents: int
    unrealized_pnl_cents: int
    source_ts: Optional[datetime] = None
    freshness_score: Optional[Decimal] = None

class RepoVerdict(str, Enum):
    DIRECT_DEPENDENCY_CANDIDATE = "DIRECT_DEPENDENCY_CANDIDATE"
    ADAPTER_TARGET = "ADAPTER_TARGET"
    REFERENCE_MINE = "REFERENCE_MINE"
    DISCOVERY_INDEX = "DISCOVERY_INDEX"
    REJECT_LICENSE = "REJECT_LICENSE"
    REJECT_STALE = "REJECT_STALE"
    REJECT_UNSAFE = "REJECT_UNSAFE"
    REJECT_SECRET_RISK = "REJECT_SECRET_RISK"
    REJECT_DIRECT_ORDER_BYPASS = "REJECT_DIRECT_ORDER_BYPASS"
    REJECT_DUPLICATE = "REJECT_DUPLICATE"
    REJECT_BROKEN = "REJECT_BROKEN"
    REJECT_SCRAPING_RISK = "REJECT_SCRAPING_RISK"
    REJECT_UNKNOWN = "REJECT_UNKNOWN"

class RepoCandidate(BaseModel):
    owner: str
    name: str
    url: str
    license: Optional[str] = None
    last_pushed_at: Optional[datetime] = None
    languages: dict[str, int] = {}
    verdict: RepoVerdict
    verdict_reasons: list[str]

class AdapterPlan(BaseModel):
    repo: str
    adapter_name: str
    emits_native_types: bool
    notes: str

class ProofReference(BaseModel):
    ref_id: str
    timestamp: datetime
    component: str
    verdict: str
    payload_hash: str

class DecisionTrace(BaseModel):
    trace_id: str
    timestamp: datetime
    mode: AccountMode
    forecast_ref: str
    strategy_ref: str
    proposal_id: str
    firewall_verdict: FirewallVerdict


class Fill(BaseModel):
    fill_id: str
    market_ticker: str
    contract_ticker: str
    side: str
    count: int
    price_cents: int
    timestamp: datetime
    source_ts: Optional[datetime] = None
    freshness_score: Optional[Decimal] = None


class RestingOrder(BaseModel):
    order_id: str
    market_ticker: str
    contract_ticker: str
    side: str
    action: str
    type: str
    count: int
    price_cents: int
    status: str
    created_at: datetime
    source_ts: Optional[datetime] = None
    freshness_score: Optional[Decimal] = None


class KalshiAccount(BaseModel):
    user_id: str
    email: str
    balance_cents: int
    available_cents: int
    portfolio_witness: Optional[str] = None
    source_ts: Optional[datetime] = None
    freshness_score: Optional[Decimal] = None


class Contract(BaseModel):
    ticker: str
    title: str
    status: str
    yes_bid: Optional[int] = None
    yes_ask: Optional[int] = None
    last_price: Optional[int] = None
    source_ts: Optional[datetime] = None


class Market(BaseModel):
    ticker: str
    title: str
    status: str
    category: str
    event_ticker: str
    contracts: list[Contract] = Field(default_factory=list)
    source_ts: Optional[datetime] = None
    freshness_score: Optional[Decimal] = None


class Event(BaseModel):
    ticker: str
    title: str
    category: str
    status: str
    markets: list[Market] = Field(default_factory=list)
    source_ts: Optional[datetime] = None
    freshness_score: Optional[Decimal] = None


class ForecastInput(BaseModel):
    market_ticker: str
    contract_ticker: str
    yes_bid: int
    yes_ask: int
    timestamp: datetime
    volume: Optional[int] = None
    open_interest: Optional[int] = None
    freshness_score: Optional[Decimal] = None
