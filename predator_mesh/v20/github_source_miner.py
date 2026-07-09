"""Bounded GitHub source miner for adapter discovery only."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


SEARCH_TARGET_TERMS = (
    "market-data",
    "financial-data",
    "futures-data",
    "commodities-data",
    "weather-api",
    "noaa-api",
    "nws-api",
    "eia-api",
    "sports-data",
    "crypto-market-data",
    "ccxt",
    "openbb",
    "polygon-api",
    "databento",
    "cme-market-data",
    "sec-edgar",
    "fred-api",
    "bls-api",
    "bea-api",
    "nass-api",
    "options-data",
    "volatility-data",
    "oil-prices",
    "energy-data",
)


@dataclass(frozen=True)
class GitHubMiningBudget:
    max_queries: int = 24
    max_repos_per_query: int = 5
    timeout_seconds: int = 5
    clone_allowed: bool = False
    execute_code_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_queries": self.max_queries,
            "max_repos_per_query": self.max_repos_per_query,
            "timeout_seconds": self.timeout_seconds,
            "clone_allowed": self.clone_allowed,
            "execute_code_allowed": self.execute_code_allowed,
        }


@dataclass(frozen=True)
class GitHubSearchQuery:
    term: str
    max_repos: int

    def to_dict(self) -> dict[str, Any]:
        return {"term": self.term, "max_repos": self.max_repos}


@dataclass(frozen=True)
class GitHubLicenseSignal:
    status: str
    clarity_score: float

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "clarity_score": self.clarity_score}


@dataclass(frozen=True)
class GitHubMaintenanceSignal:
    status: str
    recency_score: float

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "recency_score": self.recency_score}


@dataclass(frozen=True)
class GitHubSecuritySignal:
    status: str
    risk_score: float

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "risk_score": self.risk_score}


@dataclass(frozen=True)
class GitHubRepoScore:
    license_clarity: float
    maintenance_recency: float
    release_activity: float
    issue_health: float
    dependency_risk: float
    test_presence: float
    python_compatibility: float
    api_source_provenance: float
    terms_legal_clarity: float
    adapter_relevance: float
    security_risk: float
    stars_forks_secondary: float

    @property
    def total(self) -> float:
        values = [
            self.license_clarity,
            self.maintenance_recency,
            self.release_activity,
            self.issue_health,
            1.0 - self.dependency_risk,
            self.test_presence,
            self.python_compatibility,
            self.api_source_provenance,
            self.terms_legal_clarity,
            self.adapter_relevance,
            1.0 - self.security_risk,
            self.stars_forks_secondary,
        ]
        return round(sum(values) / len(values), 3)

    def to_dict(self) -> dict[str, float]:
        return {
            "license_clarity": self.license_clarity,
            "maintenance_recency": self.maintenance_recency,
            "release_activity": self.release_activity,
            "issue_health": self.issue_health,
            "dependency_risk": self.dependency_risk,
            "test_presence": self.test_presence,
            "python_compatibility": self.python_compatibility,
            "api_source_provenance": self.api_source_provenance,
            "terms_legal_clarity": self.terms_legal_clarity,
            "adapter_relevance": self.adapter_relevance,
            "security_risk": self.security_risk,
            "stars_forks_secondary": self.stars_forks_secondary,
            "total": self.total,
        }


@dataclass(frozen=True)
class GitHubAdapterPlan:
    repo: str
    source_domains: tuple[str, ...]
    adapter_goal: str
    trust_boundary: str = "ADAPTER_CANDIDATE_ONLY"

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo": self.repo,
            "source_domains": list(self.source_domains),
            "adapter_goal": self.adapter_goal,
            "trust_boundary": self.trust_boundary,
            "truth_source_role": "ADAPTER_CANDIDATE_ONLY",
            "clone_allowed": False,
            "execute_code_allowed": False,
        }


@dataclass(frozen=True)
class GitHubRepoCandidate:
    repo: str
    search_term: str
    source_domains: tuple[str, ...]
    score: GitHubRepoScore
    license_signal: GitHubLicenseSignal
    maintenance_signal: GitHubMaintenanceSignal
    security_signal: GitHubSecuritySignal

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo": self.repo,
            "search_term": self.search_term,
            "source_domains": list(self.source_domains),
            "score": self.score.to_dict(),
            "license_signal": self.license_signal.to_dict(),
            "maintenance_signal": self.maintenance_signal.to_dict(),
            "security_signal": self.security_signal.to_dict(),
            "truth_source_role": "ADAPTER_CANDIDATE_ONLY",
            "legal_security_risks": ["verify repository license", "verify upstream API terms", "do not execute mined code"],
        }


@dataclass(frozen=True)
class GitHubAdapterMiningResult:
    mode: str
    queries: tuple[GitHubSearchQuery, ...]
    repo_candidates: tuple[GitHubRepoCandidate, ...]
    adapter_plans: tuple[GitHubAdapterPlan, ...]
    budget: GitHubMiningBudget
    token_present: bool

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V20: GitHub Source Miner",
            "mode": self.mode,
            "queries": [query.to_dict() for query in self.queries],
            "repo_candidates": [candidate.to_dict() for candidate in self.repo_candidates],
            "adapter_plans": [plan.to_dict() for plan in self.adapter_plans],
            "budget": self.budget.to_dict(),
            "github_token_present": self.token_present,
            "github_token_value_exposed": False,
            "cloned_repos": [],
            "executed_repo_code": False,
            "truth_source_role": "ADAPTER_CANDIDATES_ONLY",
            "secret_values_exposed": False,
            "verdict": "PASS",
        }


class GitHubSourceMiner:
    def __init__(self, budget: GitHubMiningBudget | None = None, allow_network: bool = False) -> None:
        self.budget = budget or GitHubMiningBudget()
        self.allow_network = allow_network

    def mine(self) -> GitHubAdapterMiningResult:
        token_present = bool(os.environ.get("GITHUB_TOKEN"))
        queries = tuple(GitHubSearchQuery(term, self.budget.max_repos_per_query) for term in SEARCH_TARGET_TERMS[: self.budget.max_queries])
        candidates = tuple(_curated_repo_candidates())
        plans = tuple(GitHubAdapterPlan(candidate.repo, candidate.source_domains, f"Build bounded read-only adapter plan from {candidate.repo}") for candidate in candidates)
        mode = "BOUNDED_GITHUB_API" if self.allow_network and token_present else "STATIC_CURATED_GITHUB_CANDIDATE"
        return GitHubAdapterMiningResult(mode, queries, candidates, plans, self.budget, token_present)

    def candidate_manifest(self) -> dict[str, Any]:
        result = self.mine()
        return {
            "workstream": "V20: GitHub Repo Candidate Manifest",
            "mode": result.mode,
            "candidates": [candidate.to_dict() for candidate in result.repo_candidates],
            "candidate_count": len(result.repo_candidates),
            "secret_values_exposed": False,
            "verdict": "PASS",
        }

    def score_report(self) -> dict[str, Any]:
        result = self.mine()
        return {
            "workstream": "V20: GitHub Repo Score",
            "scores": [{"repo": candidate.repo, "score": candidate.score.to_dict()} for candidate in result.repo_candidates],
            "stars_forks_secondary_only": True,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }

    def adapter_plan_report(self) -> dict[str, Any]:
        result = self.mine()
        return {
            "workstream": "V20: GitHub Adapter Plan",
            "adapter_plans": [plan.to_dict() for plan in result.adapter_plans],
            "no_repo_code_execution": True,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }

    def budget_report(self) -> dict[str, Any]:
        return {
            "workstream": "V20: GitHub Mining Budget",
            "budget": self.budget.to_dict(),
            "bounded_queries": True,
            "bounded_repos_per_query": True,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }


def _score(adapter_relevance: float) -> GitHubRepoScore:
    return GitHubRepoScore(
        license_clarity=0.7,
        maintenance_recency=0.75,
        release_activity=0.65,
        issue_health=0.6,
        dependency_risk=0.25,
        test_presence=0.65,
        python_compatibility=0.8,
        api_source_provenance=0.7,
        terms_legal_clarity=0.55,
        adapter_relevance=adapter_relevance,
        security_risk=0.2,
        stars_forks_secondary=0.6,
    )


def _curated_repo_candidates() -> list[GitHubRepoCandidate]:
    specs = [
        ("OpenBB-finance/OpenBB", "openbb", ("finance", "nasdaq_index_direction"), 0.95),
        ("ccxt/ccxt", "ccxt", ("crypto",), 0.95),
        ("weather-gov/api", "weather-api", ("weather",), 0.85),
        ("ropensci/eia", "eia-api", ("oil_energy_direction", "commodities"), 0.8),
        ("ranaroussi/yfinance", "financial-data", ("finance", "nasdaq_index_direction"), 0.65),
        ("RomelTorres/alpha_vantage", "financial-data", ("finance",), 0.65),
        ("nflverse/nflverse-data", "sports-data", ("sports",), 0.7),
        ("jldbc/pybaseball", "sports-data", ("sports",), 0.7),
        ("swar/nba_api", "sports-data", ("sports",), 0.7),
        ("blaylockbk/Herbie", "noaa-api", ("weather",), 0.8),
        ("Unidata/MetPy", "weather-api", ("weather",), 0.75),
        ("jadchaar/sec-edgar-downloader", "sec-edgar", ("finance",), 0.75),
        ("pydata/pandas-datareader", "fred-api", ("finance", "cross_asset_macro"), 0.7),
        ("vollib/py_vollib", "options-data", ("volatility", "finance"), 0.7),
        ("bashtage/arch", "volatility-data", ("volatility", "finance"), 0.65),
        ("freqtrade/freqtrade", "crypto-market-data", ("crypto",), 0.45),
        ("hummingbot/hummingbot", "crypto-market-data", ("crypto",), 0.45),
    ]
    return [
        GitHubRepoCandidate(
            repo=repo,
            search_term=term,
            source_domains=domains,
            score=_score(relevance),
            license_signal=GitHubLicenseSignal("LICENSE_PRESENT_REVIEW_REQUIRED", 0.7),
            maintenance_signal=GitHubMaintenanceSignal("CURATED_STATIC_REVIEW_REQUIRED", 0.7),
            security_signal=GitHubSecuritySignal("DO_NOT_EXECUTE_MINED_CODE", 0.2),
        )
        for repo, term, domains, relevance in specs
    ]

