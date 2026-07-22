from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, Field


class ForecastRecord(BaseModel):
    """V1 forecast record kept for backward compatibility."""

    market_ticker: str
    contract_ticker: str
    dummy_probability: Decimal
    confidence_score: Decimal
    uncertainty_band: tuple[Decimal, Decimal]
    timestamp: datetime
    proof_reference: str


class SettlementRecord(BaseModel):
    market_ticker: str
    contract_ticker: str
    outcome: int = Field(ge=0, le=1)
    settled_at: datetime
    source: str


class CalibrationMetrics(BaseModel):
    """V1 calibration metrics kept for backward compatibility."""

    market_ticker: str
    contract_ticker: str
    brier_score: float | None = None
    log_loss: float | None = None
    calibration_error: float | None = None
    coverage: float | None = None
    sample_count: int = 0
    generated_at: datetime = Field(default_factory=lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc))


class ConfidenceBucket(str, Enum):
    HIGH = "high"  # >= 0.7
    MEDIUM = "medium"  # 0.4 - 0.7
    LOW = "low"  # < 0.4


class ForecastRecordV2(BaseModel):
    """V2 forecast record with multi-model probabilities and settlement tracking."""

    forecast_id: str
    market_ticker: str
    contract_ticker: str
    category: str | None = None
    horizon: str | None = None
    model_route: str
    market_implied_probability: Decimal
    dummy_probability: Decimal
    deepseekv4flash_probability: Decimal | None = None
    minimaxm3_probability: Decimal | None = None
    final_probability: Decimal
    confidence_bucket: str
    timestamp: datetime
    settlement_status: str = "open"  # "open" or "settled"
    realized_outcome: int | None = None  # 0 or 1 once settled
    no_trade_reason: str | None = None

    def model_probabilities(self) -> list[Decimal]:
        """Return available model probabilities for disagreement scoring."""
        probs: list[Decimal] = [self.dummy_probability]
        if self.deepseekv4flash_probability is not None:
            probs.append(self.deepseekv4flash_probability)
        if self.minimaxm3_probability is not None:
            probs.append(self.minimaxm3_probability)
        return probs


class CalibrationMetricsV2(BaseModel):
    """V2 calibration metrics for multi-model probability scoring."""

    market_ticker: str
    contract_ticker: str
    brier_score: float | None = None
    log_loss: float | None = None
    expected_calibration_error: float | None = None
    maximum_calibration_error: float | None = None
    market_implied_delta: float | None = None
    model_disagreement_score: float | None = None
    confidence_bucket_accuracy: dict[str, float] = Field(default_factory=dict)
    abstention_count: int = 0
    abstention_rate: float = 0.0
    no_trade_reasons: dict[str, int] = Field(default_factory=dict)
    sample_count: int = 0
    settled_count: int = 0
    generated_at: datetime = Field(default_factory=lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc))
