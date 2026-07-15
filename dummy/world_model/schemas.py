"""Horizon- and league-specific world-state schemas for DUMMY vNext."""

from __future__ import annotations

from functools import lru_cache

from dummy.agents import AgentVertical
from dummy.chronos import ClockDomain

from .models import (
    MissingDataPolicy,
    StateLayer,
    WorldDomain,
    WorldFieldSpec,
    WorldModelValidationError,
    WorldStateSchema,
)


CRYPTO_CLOCKS = (
    ClockDomain.QUOTE,
    ClockDomain.ONE_MINUTE,
    ClockDomain.FIVE_MINUTE,
    ClockDomain.FIFTEEN_MINUTE,
    ClockDomain.HOURLY,
    ClockDomain.DAILY,
    ClockDomain.WEEKLY,
    ClockDomain.EXPIRY,
)
SPORT_VERTICALS = (
    AgentVertical.MLB,
    AgentVertical.NBA,
    AgentVertical.NFL,
    AgentVertical.NCAAF,
    AgentVertical.NHL,
    AgentVertical.NCAAMB,
)
SPORT_CLOCKS_BY_VERTICAL = {
    AgentVertical.MLB: (
        ClockDomain.PREGAME,
        ClockDomain.LINEUP_CONFIRMATION,
        ClockDomain.WARMUP,
        ClockDomain.GAME_START,
        ClockDomain.INNING,
    ),
    AgentVertical.NBA: (
        ClockDomain.PREGAME,
        ClockDomain.LINEUP_CONFIRMATION,
        ClockDomain.WARMUP,
        ClockDomain.GAME_START,
        ClockDomain.POSSESSION,
        ClockDomain.PERIOD,
        ClockDomain.HALFTIME,
        ClockDomain.OVERTIME,
    ),
    AgentVertical.NFL: (
        ClockDomain.PREGAME,
        ClockDomain.LINEUP_CONFIRMATION,
        ClockDomain.WARMUP,
        ClockDomain.GAME_START,
        ClockDomain.POSSESSION,
        ClockDomain.PERIOD,
        ClockDomain.HALFTIME,
        ClockDomain.OVERTIME,
    ),
    AgentVertical.NCAAF: (
        ClockDomain.PREGAME,
        ClockDomain.LINEUP_CONFIRMATION,
        ClockDomain.WARMUP,
        ClockDomain.GAME_START,
        ClockDomain.POSSESSION,
        ClockDomain.PERIOD,
        ClockDomain.HALFTIME,
        ClockDomain.OVERTIME,
    ),
    AgentVertical.NHL: (
        ClockDomain.PREGAME,
        ClockDomain.LINEUP_CONFIRMATION,
        ClockDomain.WARMUP,
        ClockDomain.GAME_START,
        ClockDomain.POSSESSION,
        ClockDomain.PERIOD,
        ClockDomain.OVERTIME,
    ),
    AgentVertical.NCAAMB: (
        ClockDomain.PREGAME,
        ClockDomain.LINEUP_CONFIRMATION,
        ClockDomain.WARMUP,
        ClockDomain.GAME_START,
        ClockDomain.POSSESSION,
        ClockDomain.PERIOD,
        ClockDomain.HALFTIME,
        ClockDomain.OVERTIME,
    ),
}


def _field(
    key: str,
    description: str,
    unit: str,
    *,
    lease_ms: int,
    critical: bool = False,
    layers: tuple[StateLayer, ...] = (StateLayer.DERIVED,),
    missing_policy: MissingDataPolicy = MissingDataPolicy.EXPLICIT_UNKNOWN,
) -> WorldFieldSpec:
    return WorldFieldSpec(
        key=key,
        description=description,
        unit=unit,
        critical=critical,
        lease_ms=lease_ms,
        allowed_layers=layers,
        missing_policy=(MissingDataPolicy.ABSTAIN if critical else missing_policy),
    )


def _lease_for(clock: ClockDomain) -> int:
    return {
        ClockDomain.QUOTE: 10_000,
        ClockDomain.ONE_MINUTE: 30_000,
        ClockDomain.FIVE_MINUTE: 60_000,
        ClockDomain.FIFTEEN_MINUTE: 120_000,
        ClockDomain.HOURLY: 300_000,
        ClockDomain.DAILY: 900_000,
        ClockDomain.WEEKLY: 3_600_000,
        ClockDomain.EXPIRY: 60_000,
        ClockDomain.PREGAME: 900_000,
        ClockDomain.LINEUP_CONFIRMATION: 300_000,
        ClockDomain.WARMUP: 180_000,
        ClockDomain.GAME_START: 60_000,
        ClockDomain.POSSESSION: 15_000,
        ClockDomain.INNING: 30_000,
        ClockDomain.PERIOD: 20_000,
        ClockDomain.HALFTIME: 120_000,
        ClockDomain.OVERTIME: 10_000,
    }[clock]


def _common_fields(lease_ms: int) -> tuple[WorldFieldSpec, ...]:
    fact = (StateLayer.FACT,)
    return (
        _field(
            "market.status",
            "Exchange market status observed at the decision clock.",
            "enum",
            lease_ms=lease_ms,
            critical=True,
            layers=fact,
        ),
        _field(
            "market.yes_bid_cents",
            "Best witnessed YES bid in cents.",
            "cents",
            lease_ms=lease_ms,
            critical=True,
            layers=fact,
        ),
        _field(
            "market.yes_ask_cents",
            "Best witnessed YES ask in cents.",
            "cents",
            lease_ms=lease_ms,
            critical=True,
            layers=fact,
        ),
        _field(
            "market.no_bid_cents",
            "Best witnessed NO bid in cents.",
            "cents",
            lease_ms=lease_ms,
            critical=True,
            layers=fact,
        ),
        _field(
            "market.no_ask_cents",
            "Best witnessed NO ask in cents.",
            "cents",
            lease_ms=lease_ms,
            critical=True,
            layers=fact,
        ),
        _field(
            "market.yes_ask_depth",
            "Witnessed contracts available at the YES ask.",
            "contracts",
            lease_ms=lease_ms,
            critical=True,
            layers=fact,
        ),
        _field(
            "market.no_ask_depth",
            "Witnessed contracts available at the NO ask.",
            "contracts",
            lease_ms=lease_ms,
            critical=True,
            layers=fact,
        ),
        _field(
            "incumbent.probability_yes",
            "Frozen incumbent probability for the YES outcome.",
            "probability",
            lease_ms=lease_ms,
            critical=True,
            layers=(StateLayer.HYPOTHESIS,),
        ),
        _field(
            "incumbent.uncertainty",
            "Frozen incumbent uncertainty supplied with its forecast.",
            "probability",
            lease_ms=lease_ms,
            critical=True,
            layers=(StateLayer.DERIVED,),
        ),
        _field(
            "incumbent.feature_manifest",
            "Exact frozen feature payload used by the incumbent adapter.",
            "json",
            lease_ms=lease_ms,
            layers=(StateLayer.DERIVED,),
            missing_policy=MissingDataPolicy.EXPLICIT_UNKNOWN,
        ),
    )


def _crypto_fields(lease_ms: int) -> tuple[WorldFieldSpec, ...]:
    definitions = (
        ("crypto.realized_volatility", "Point-in-time realized volatility.", "annualized_volatility"),
        ("crypto.implied_volatility", "Point-in-time implied volatility.", "annualized_volatility"),
        ("crypto.liquidity", "Cross-venue executable liquidity state.", "json"),
        ("crypto.leverage", "Observed leverage proxy.", "ratio"),
        ("crypto.funding", "Perpetual funding state.", "rate"),
        ("crypto.open_interest", "Open-interest state.", "notional"),
        ("crypto.order_book_imbalance", "Order-book imbalance.", "ratio"),
        ("crypto.cross_venue_dislocation", "Cross-venue price dislocation.", "basis_points"),
        ("crypto.liquidation_pressure", "Liquidation-pressure state.", "score"),
        ("crypto.spot_trend", "Spot trend at the schema horizon.", "score"),
        ("crypto.macro_risk", "Macro risk state.", "score"),
        ("crypto.dollar_rates_regime", "Dollar and rates regime.", "enum"),
        ("crypto.equity_commodity_correlation", "Cross-asset correlation regime.", "json"),
        ("crypto.weekend_liquidity", "Weekend-liquidity regime.", "score"),
        (
            "crypto.horizon_uncertainty",
            "Log-return sigma at the forecast horizon.",
            "log_return_sigma",
        ),
    )
    return tuple(
        _field(
            key,
            description,
            unit,
            lease_ms=lease_ms,
            missing_policy=MissingDataPolicy.WIDEN_UNCERTAINTY,
        )
        for key, description, unit in definitions
    )


def _sport_fields(lease_ms: int) -> tuple[WorldFieldSpec, ...]:
    definitions = (
        ("sport.team_strength", "Point-in-time team-strength state.", "json"),
        ("sport.player_availability", "Confirmed player availability.", "json"),
        ("sport.starter_certainty", "Starter identity and certainty.", "probability"),
        ("sport.fatigue", "Team fatigue state.", "json"),
        ("sport.rest", "Rest differential.", "days"),
        ("sport.travel", "Travel burden.", "json"),
        ("sport.weather", "Venue weather state.", "json"),
        ("sport.venue", "Venue state.", "json"),
        ("sport.officiating", "Assigned officiating state.", "json"),
        ("sport.tactical_matchup", "Tactical matchup state.", "json"),
        ("sport.live_possession", "Live possession or control state.", "json"),
        ("sport.scoring_environment", "Expected scoring environment.", "json"),
        ("sport.market_disagreement", "Independent market disagreement.", "probability"),
        ("sport.season_phase", "Season and tournament phase.", "enum"),
        ("sport.schedule_congestion", "Schedule congestion.", "json"),
        ("sport.overtime_rules", "Applicable overtime rules.", "json"),
        ("sport.lineup_confirmation_quality", "Lineup confirmation quality.", "probability"),
    )
    widen = {
        "sport.player_availability",
        "sport.starter_certainty",
        "sport.weather",
        "sport.lineup_confirmation_quality",
    }
    return tuple(
        _field(
            key,
            description,
            unit,
            lease_ms=lease_ms,
            missing_policy=(
                MissingDataPolicy.WIDEN_UNCERTAINTY
                if key in widen
                else MissingDataPolicy.EXPLICIT_UNKNOWN
            ),
        )
        for key, description, unit in definitions
    )


def _league_fields(domain: WorldDomain, lease_ms: int) -> tuple[WorldFieldSpec, ...]:
    if domain is WorldDomain.MLB:
        definitions = (
            ("mlb.starting_pitchers", "Confirmed starting pitchers."),
            ("mlb.bullpen_availability", "Bullpen availability and recent workload."),
            ("mlb.park_run_environment", "Park-specific run environment."),
            ("mlb.inning_base_out_state", "Live inning, base, and out state."),
        )
    elif domain in {WorldDomain.NBA, WorldDomain.NCAAMB}:
        prefix = domain.value
        definitions = (
            (f"{prefix}.pace", "Possession pace state."),
            (f"{prefix}.foul_environment", "Foul and bonus environment."),
            (f"{prefix}.three_point_variance", "Three-point variance state."),
        )
    elif domain in {WorldDomain.NFL, WorldDomain.NCAAF}:
        prefix = domain.value
        definitions = (
            (f"{prefix}.quarterback_status", "Quarterback status and certainty."),
            (f"{prefix}.offensive_line_availability", "Offensive-line availability."),
            (f"{prefix}.field_position", "Live field-position state."),
            (f"{prefix}.down_distance", "Live down-and-distance state."),
        )
    elif domain is WorldDomain.NHL:
        definitions = (
            ("nhl.goaltender_status", "Goaltender identity and status."),
            ("nhl.empty_net_state", "Pulled-goaltender and empty-net state."),
            ("nhl.shot_quality", "Shot-quality and expected-goal state."),
        )
    else:
        raise WorldModelValidationError(f"unsupported sports domain: {domain.value}")
    return tuple(
        _field(
            key,
            description,
            "json",
            lease_ms=lease_ms,
            missing_policy=MissingDataPolicy.WIDEN_UNCERTAINTY,
        )
        for key, description in definitions
    )


@lru_cache(maxsize=None)
def schema_for(
    vertical: AgentVertical,
    clock_domain: ClockDomain,
) -> WorldStateSchema:
    """Resolve one deterministic schema for an allowed horizon and league."""

    lease_ms = _lease_for(clock_domain)
    if vertical is AgentVertical.CRYPTO:
        if clock_domain not in CRYPTO_CLOCKS:
            raise WorldModelValidationError(
                f"unsupported crypto world-model clock: {clock_domain.value}"
            )
        domain = WorldDomain.CRYPTO
        fields = (*_common_fields(lease_ms), *_crypto_fields(lease_ms))
        scope = f"crypto_horizon:{clock_domain.value}"
    elif vertical in SPORT_VERTICALS:
        if clock_domain not in SPORT_CLOCKS_BY_VERTICAL[vertical]:
            raise WorldModelValidationError(
                f"unsupported sports world-model clock: {clock_domain.value}"
            )
        domain = WorldDomain(vertical.value)
        fields = (
            *_common_fields(lease_ms),
            *_sport_fields(lease_ms),
            *_league_fields(domain, lease_ms),
        )
        scope = f"league:{domain.value};clock:{clock_domain.value}"
    else:
        raise WorldModelValidationError(
            f"vertical has no Phase 4 world model: {vertical.value}"
        )
    return WorldStateSchema(
        schema_id=f"dummy-{domain.value}-{clock_domain.value}-world-state-v1",
        schema_version="1.0.0",
        domain=domain,
        scope=scope,
        fields=fields,
    )


def supported_schema_manifest() -> dict[str, object]:
    schemas = [schema_for(AgentVertical.CRYPTO, clock) for clock in CRYPTO_CLOCKS]
    schemas.extend(
        schema_for(vertical, clock)
        for vertical in SPORT_VERTICALS
        for clock in SPORT_CLOCKS_BY_VERTICAL[vertical]
    )
    catalog = [
        {
            "schema_id": item.schema_id,
            "schema_version": item.schema_version,
            "domain": item.domain.value,
            "scope": item.scope,
            "field_count": len(item.fields),
            "critical_fields": [
                field.key for field in item.fields if field.critical
            ],
            "schema_digest": item.digest(),
        }
        for item in schemas
    ]
    return {
        "schema_version": 1,
        "catalog_kind": "content_addressed_world_state_schemas",
        "authoritative_definitions": "dummy.world_model.schemas:schema_for",
        "schemas": catalog,
        "schema_digests": {item.schema_id: item.digest() for item in schemas},
    }
