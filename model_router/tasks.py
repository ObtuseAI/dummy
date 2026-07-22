from enum import Enum


class ModelTask(str, Enum):
    FORECAST_OPINION = "forecast_opinion"
    RAPID_FORECAST = "rapid_forecast"
    STRATEGY_CRITIQUE = "strategy_critique"
    RISK_CRITIQUE = "risk_critique"
    NO_TRADE_REASON = "no_trade_reason"
    TRADE_DRAFT = "trade_draft"
    CALIBRATION_NOTE = "calibration_note"
    MARKET_THESIS = "market_thesis"
    REFLECTION_LESSONS = "reflection_lessons"
    HYBRID_REVIEW = "hybrid_review"
