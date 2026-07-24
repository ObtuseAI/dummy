"""Single-order cap + compliance precheck. NOT the risk brain.

Naming trap (2026-07-24 audit): "governor" reads like the system's risk
authority, but this module is only the two stateless per-order checks below.
The real risk engine -- bankroll staging, drawdown ladder, exposure and
correlated-group limits, position caps, self-stop -- is
``autonomy/risk_brain.py`` (state in ``autonomy/risk_state.py``, consumed by
``autonomy/allocator.py``), and the final live-submit authority is
``live_firewall/firewall.py``. Nothing here sizes a position or grants
execution authority.

The module keeps its name because ~295 archived ``predator_mesh/vNN``
milestone snapshots import this exact path and are required to stay
byte-identical; renaming it would rewrite history rather than fix a bug.
"""
from core.ontology import RiskVerdict, TradeProposal, CapConfig


def assess_trade_risk(proposal: TradeProposal, caps: CapConfig) -> RiskVerdict:
    order_value = proposal.price_cents * proposal.size
    if order_value > caps.max_single_order_cents:
        return RiskVerdict(passed=False, reason="Single order cap breach", metrics={"order_cents": order_value})
    if not proposal.compliance_verdict.passed:
        return RiskVerdict(passed=False, reason="Compliance gate failed", metrics={"blocked": proposal.compliance_verdict.blocked_categories})
    return RiskVerdict(passed=True, reason="Risk checks passed", metrics={"order_cents": order_value})
