"""Canonical complete Phase 7 arena scenario catalog."""

from __future__ import annotations

from typing import Any

from dummy.arenas.models import (
    ArenaCategory,
    ArenaDomain,
    ArenaResponse,
    ArenaScenario,
    StressSignal,
)
from dummy.world_model.models import digest_json


_R = ArenaResponse

_SCENARIOS: tuple[
    tuple[str, ArenaDomain, ArenaCategory, StressSignal, float, tuple[ArenaResponse, ...]],
    ...,
] = (
    ("market-prior arena", ArenaDomain.FORECAST, ArenaCategory.MARKET_PRIOR, StressSignal.MARKET_PRIOR_CONFLICT, 0.75, (_R.INCREASE_MARKET_ANCHOR, _R.WIDEN_UNCERTAINTY)),
    ("random-entry arena", ArenaDomain.FORECAST, ArenaCategory.CALIBRATION, StressSignal.DATA_INTEGRITY, 0.90, (_R.ABSTAIN, _R.REQUEST_EVIDENCE)),
    ("stale-data arena", ArenaDomain.FORECAST, ArenaCategory.DRIFT, StressSignal.STALE_OR_MISSING, 0.85, (_R.ABSTAIN, _R.REQUEST_REFRESH)),
    ("missing-source arena", ArenaDomain.FORECAST, ArenaCategory.LEAKAGE, StressSignal.STALE_OR_MISSING, 0.90, (_R.ABSTAIN, _R.REQUEST_EVIDENCE, _R.REQUEST_REFRESH)),
    ("line-movement arena", ArenaDomain.FORECAST, ArenaCategory.MARKET_PRIOR, StressSignal.MARKET_PRIOR_CONFLICT, 0.70, (_R.INCREASE_MARKET_ANCHOR, _R.WIDEN_UNCERTAINTY)),
    ("alternate-strike arena", ArenaDomain.FORECAST, ArenaCategory.ADVERSARIAL, StressSignal.DATA_INTEGRITY, 0.65, (_R.REQUEST_EVIDENCE, _R.WIDEN_UNCERTAINTY)),
    ("extreme-spread arena", ArenaDomain.FORECAST, ArenaCategory.CALIBRATION, StressSignal.VOLATILITY_SHOCK, 0.80, (_R.ABSTAIN, _R.WIDEN_UNCERTAINTY)),
    ("low-liquidity arena", ArenaDomain.FORECAST, ArenaCategory.LIQUIDITY, StressSignal.LIQUIDITY, 0.90, (_R.ABSTAIN, _R.MARK_EXECUTION_IRRELEVANT)),
    ("regime-shift arena", ArenaDomain.FORECAST, ArenaCategory.REGIME, StressSignal.REGIME_SHIFT, 0.90, (_R.ABSTAIN, _R.QUARANTINE, _R.WIDEN_UNCERTAINTY)),
    ("news-shock arena", ArenaDomain.FORECAST, ArenaCategory.ADVERSARIAL, StressSignal.VOLATILITY_SHOCK, 0.95, (_R.ABSTAIN, _R.REQUEST_REFRESH, _R.WIDEN_UNCERTAINTY)),
    ("correlated-source arena", ArenaDomain.FORECAST, ArenaCategory.LEAKAGE, StressSignal.CONCENTRATION, 0.85, (_R.CAP_INFLUENCE, _R.INCREASE_MARKET_ANCHOR)),
    ("late scratch", ArenaDomain.SPORTS, ArenaCategory.DRIFT, StressSignal.STALE_OR_MISSING, 0.90, (_R.ABSTAIN, _R.REQUEST_REFRESH)),
    ("lineup mismatch", ArenaDomain.SPORTS, ArenaCategory.LEAKAGE, StressSignal.DATA_INTEGRITY, 0.90, (_R.ABSTAIN, _R.QUARANTINE, _R.REQUEST_EVIDENCE)),
    ("weather surprise", ArenaDomain.SPORTS, ArenaCategory.REGIME, StressSignal.REGIME_SHIFT, 0.80, (_R.ABSTAIN, _R.REQUEST_REFRESH, _R.WIDEN_UNCERTAINTY)),
    ("overtime", ArenaDomain.SPORTS, ArenaCategory.ADVERSARIAL, StressSignal.DATA_INTEGRITY, 0.85, (_R.ABSTAIN, _R.REQUEST_EVIDENCE)),
    ("ejection", ArenaDomain.SPORTS, ArenaCategory.DRIFT, StressSignal.STALE_OR_MISSING, 0.95, (_R.ABSTAIN, _R.REQUEST_REFRESH)),
    ("malformed book", ArenaDomain.SPORTS, ArenaCategory.MARKET_PRIOR, StressSignal.DATA_INTEGRITY, 1.00, (_R.QUARANTINE, _R.VETO)),
    ("incomplete drive state", ArenaDomain.SPORTS, ArenaCategory.LEAKAGE, StressSignal.STALE_OR_MISSING, 0.95, (_R.ABSTAIN, _R.REQUEST_EVIDENCE)),
    ("goalie change", ArenaDomain.SPORTS, ArenaCategory.DRIFT, StressSignal.STALE_OR_MISSING, 0.90, (_R.ABSTAIN, _R.REQUEST_REFRESH)),
    ("bullpen exhaustion", ArenaDomain.SPORTS, ArenaCategory.REGIME, StressSignal.REGIME_SHIFT, 0.75, (_R.REQUEST_EVIDENCE, _R.WIDEN_UNCERTAINTY)),
    ("confirmed-lineup failure", ArenaDomain.SPORTS, ArenaCategory.LEAKAGE, StressSignal.DATA_INTEGRITY, 1.00, (_R.ABSTAIN, _R.VETO)),
    ("sudden volatility spike", ArenaDomain.CRYPTO, ArenaCategory.REGIME, StressSignal.VOLATILITY_SHOCK, 0.95, (_R.ABSTAIN, _R.WIDEN_UNCERTAINTY)),
    ("exchange divergence", ArenaDomain.CRYPTO, ArenaCategory.MARKET_PRIOR, StressSignal.MARKET_PRIOR_CONFLICT, 0.85, (_R.INCREASE_MARKET_ANCHOR, _R.REQUEST_EVIDENCE, _R.WIDEN_UNCERTAINTY)),
    ("order-book vacuum", ArenaDomain.CRYPTO, ArenaCategory.LIQUIDITY, StressSignal.LIQUIDITY, 1.00, (_R.ABSTAIN, _R.MARK_EXECUTION_IRRELEVANT)),
    ("liquidation cascade", ArenaDomain.CRYPTO, ArenaCategory.REGIME, StressSignal.VOLATILITY_SHOCK, 1.00, (_R.ABSTAIN, _R.QUARANTINE, _R.WIDEN_UNCERTAINTY)),
    ("funding inversion", ArenaDomain.CRYPTO, ArenaCategory.REGIME, StressSignal.REGIME_SHIFT, 0.80, (_R.REQUEST_EVIDENCE, _R.WIDEN_UNCERTAINTY)),
    ("macro shock", ArenaDomain.CRYPTO, ArenaCategory.ADVERSARIAL, StressSignal.REGIME_SHIFT, 0.95, (_R.ABSTAIN, _R.REQUEST_REFRESH, _R.WIDEN_UNCERTAINTY)),
    ("weekend illiquidity", ArenaDomain.CRYPTO, ArenaCategory.LIQUIDITY, StressSignal.LIQUIDITY, 0.85, (_R.ABSTAIN, _R.MARK_EXECUTION_IRRELEVANT)),
    ("stale options surface", ArenaDomain.CRYPTO, ArenaCategory.DRIFT, StressSignal.STALE_OR_MISSING, 0.90, (_R.ABSTAIN, _R.REQUEST_REFRESH)),
    ("false breakout", ArenaDomain.CRYPTO, ArenaCategory.ADVERSARIAL, StressSignal.MARKET_PRIOR_CONFLICT, 0.75, (_R.INCREASE_MARKET_ANCHOR, _R.WIDEN_UNCERTAINTY)),
    ("cross-venue outage", ArenaDomain.CRYPTO, ArenaCategory.EXECUTION, StressSignal.EXECUTION_REALISM, 1.00, (_R.ABSTAIN, _R.MARK_EXECUTION_IRRELEVANT, _R.REQUEST_REFRESH)),
    ("overconfidence detection", ArenaDomain.METACOGNITIVE, ArenaCategory.CALIBRATION, StressSignal.METACOGNITIVE, 0.85, (_R.ABSTAIN, _R.INCREASE_MARKET_ANCHOR)),
    ("knowledge-boundary accuracy", ArenaDomain.METACOGNITIVE, ArenaCategory.META, StressSignal.METACOGNITIVE, 0.80, (_R.ABSTAIN, _R.REQUEST_EVIDENCE)),
    ("premature stopping", ArenaDomain.METACOGNITIVE, ArenaCategory.META, StressSignal.METACOGNITIVE, 0.70, (_R.REQUEST_EVIDENCE, _R.WIDEN_UNCERTAINTY)),
    ("excessive compute", ArenaDomain.METACOGNITIVE, ArenaCategory.META, StressSignal.METACOGNITIVE, 0.90, (_R.REDUCE_RESOURCE_BUDGET,)),
    ("false consensus", ArenaDomain.METACOGNITIVE, ArenaCategory.LEAKAGE, StressSignal.CONCENTRATION, 0.90, (_R.CAP_INFLUENCE, _R.INCREASE_MARKET_ANCHOR)),
    ("useless challenger spawning", ArenaDomain.METACOGNITIVE, ArenaCategory.META, StressSignal.METACOGNITIVE, 0.80, (_R.REDUCE_RESOURCE_BUDGET,)),
    ("abstention quality", ArenaDomain.METACOGNITIVE, ArenaCategory.CALIBRATION, StressSignal.METACOGNITIVE, 0.75, (_R.REQUEST_EVIDENCE,)),
    ("strategy selection", ArenaDomain.METACOGNITIVE, ArenaCategory.META, StressSignal.METACOGNITIVE, 0.75, (_R.REQUEST_EVIDENCE, _R.WIDEN_UNCERTAINTY)),
    ("calibration drift", ArenaDomain.METACOGNITIVE, ArenaCategory.DRIFT, StressSignal.METACOGNITIVE, 0.90, (_R.ABSTAIN, _R.QUARANTINE)),
)


def arena_catalog() -> tuple[ArenaScenario, ...]:
    scenarios: list[ArenaScenario] = []
    for name, domain, category, signal, severity, responses in _SCENARIOS:
        semantic = {
            "schema_version": 1,
            "name": name,
            "domain": domain.value,
            "category": category.value,
            "signal": signal.value,
            "severity": severity,
            "expected_responses": sorted(item.value for item in responses),
            "evidence_ids": [f"phase7-plan:{domain.value}:{name.replace(' ', '-')}"] ,
            "empirical": False,
        }
        scenarios.append(
            ArenaScenario(
                scenario_id=digest_json(semantic),
                name=name,
                domain=domain,
                category=category,
                signal=signal,
                severity=severity,
                expected_responses=responses,
                evidence_ids=tuple(semantic["evidence_ids"]),
            )
        )
    return tuple(sorted(scenarios, key=lambda item: item.scenario_id))


def arena_catalog_manifest() -> dict[str, Any]:
    scenarios = arena_catalog()
    body: dict[str, Any] = {
        "schema_version": 1,
        "phase": 7,
        "scenario_count": len(scenarios),
        "domains": {
            domain.value: sum(item.domain is domain for item in scenarios)
            for domain in ArenaDomain
        },
        "scenarios": [item.to_dict() for item in scenarios],
        "empirical_claim_supported": False,
        "execution_authority": False,
    }
    body["catalog_id"] = digest_json(body)
    return body


__all__ = ["arena_catalog", "arena_catalog_manifest"]
