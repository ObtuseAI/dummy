from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class NoTradeReason:
    reason: str
    category: str


@dataclass
class OutputFirewallDecision:
    safe: bool
    blocked_patterns: list[dict[str, str]]
    no_trade_reason: NoTradeReason | None


class ModelOutputFirewall:
    """Post-model firewall: block outputs that instruct trading or config changes."""

    _BLOCKED: list[tuple[str, str]] = [
        (r"submit\s+(?:a\s+)?(?:buy|sell|order)", "ORDER_INSTRUCTION_BLOCK"),
        (r"create_order", "ORDER_INSTRUCTION_BLOCK"),
        (r"call\s+(?:the\s+)?create_order", "ORDER_INSTRUCTION_BLOCK"),
        (r"modify\s+caps?\.json", "CAP_MODIFICATION_BLOCK"),
        (r"set\s+live_submit", "LIVE_SUBMIT_MODIFICATION_BLOCK"),
        (r"enable\s+live\s+submit", "LIVE_SUBMIT_MODIFICATION_BLOCK"),
        (r"bypass\s+(?:the\s+)?firewall", "FIREWALL_BYPASS_BLOCK"),
        (r"call\s+(?:kalshi\s+)?(?:create|cancel|batch)\s+order", "KALSHI_WRITE_BLOCK"),
    ]

    def check(self, output: str) -> OutputFirewallDecision:
        text = output.lower()
        blocked: list[dict[str, str]] = []
        for pattern, category in self._BLOCKED:
            if re.search(pattern, text):
                blocked.append({"pattern": pattern, "category": category})
        if blocked:
            category = blocked[0]["category"]
            return OutputFirewallDecision(
                safe=False,
                blocked_patterns=blocked,
                no_trade_reason=NoTradeReason(
                    reason=f"Model output blocked: {category}",
                    category=category,
                ),
            )
        return OutputFirewallDecision(safe=True, blocked_patterns=[], no_trade_reason=None)
