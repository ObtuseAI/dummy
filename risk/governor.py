from core.ontology import RiskVerdict, TradeProposal, CapConfig


def assess_trade_risk(proposal: TradeProposal, caps: CapConfig) -> RiskVerdict:
    order_value = proposal.price_cents * proposal.size
    if order_value > caps.max_single_order_cents:
        return RiskVerdict(passed=False, reason="Single order cap breach", metrics={"order_cents": order_value})
    if not proposal.compliance_verdict.passed:
        return RiskVerdict(passed=False, reason="Compliance gate failed", metrics={"blocked": proposal.compliance_verdict.blocked_categories})
    return RiskVerdict(passed=True, reason="Risk checks passed", metrics={"order_cents": order_value})
