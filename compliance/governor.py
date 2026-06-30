from core.ontology import ComplianceVerdict
from core.config_loader import load_caps


def assess_compliance(market_ticker: str, contract_ticker: str) -> ComplianceVerdict:
    caps = load_caps()
    blocked = [c for c in caps.blocked_categories if market_ticker.startswith(c) or contract_ticker.startswith(c)]
    if blocked:
        return ComplianceVerdict(passed=False, blocked_categories=blocked, reason=f"Blocked categories: {blocked}")
    return ComplianceVerdict(passed=True, blocked_categories=[], reason="Compliant")
