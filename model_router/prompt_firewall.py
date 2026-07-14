from __future__ import annotations
import re
from dataclasses import dataclass
from core.secret_guard import redact_text

_BLOCKED_PATTERNS = {
    "order_endpoint": [r"\bcreate_order\s*\(", r"\bcancel_order\s*\(", r"post\s+/orders", r"put\s+/orders"],
    "instruction_injection": [r"ignore\s+previous", r"disregard\s+all", r"you\s+are\s+now\s+.*operator"],
    "cap_modification": [r"max_single_order_cents", r"live_submit\.json", r"enabled\s*:\s*true"],
    "secret_leak": [r"-----begin (rsa |ec |dsa |openssh )?private key-----", r"\b[a-z0-9_]{32,}\b"],
}


class PromptFirewall:
    def __init__(self, blocked_categories: list[str], secret_env_names: list[str]):
        self.blocked_categories = set(blocked_categories)
        self.secret_env_names = secret_env_names

    def sanitize(self, prompt: str) -> str:
        prompt = redact_text(prompt)
        prompt = prompt.replace("\x00", "")
        prompt = re.sub(r"\s+", " ", prompt).strip()
        return prompt[:16000]

    def block_check(self, prompt: str) -> str | None:
        lowered = prompt.lower()
        for category, patterns in _BLOCKED_PATTERNS.items():
            if category not in self.blocked_categories:
                continue
            for pat in patterns:
                if re.search(pat, lowered):
                    return category
        for name in self.secret_env_names:
            value = __import__("os").environ.get(name)
            if value and len(value) >= 4 and value in prompt:
                return "secret_leak"
        return None

    def redact_response(self, text: str) -> str:
        return redact_text(text)


@dataclass
class FirewallDecision:
    classification: str
    allowed: bool
    matched_tokens: list[str]


class PromptFirewallV2:
    """Expanded prompt firewall with explicit classification labels."""

    CLASSIFICATIONS = {
        "SECRET_BLOCK": False,
        "ACCOUNT_DATA_BLOCK": False,
        "ORDER_INSTRUCTION_BLOCK": False,
        "FIREWALL_BYPASS_BLOCK": False,
        "CAP_MODIFICATION_BLOCK": False,
        "LIVE_SUBMIT_MODIFICATION_BLOCK": False,
        "SAFE_SANITIZED_MARKET_PROMPT": True,
    }

    _PATTERNS: list[tuple[str, list[str]]] = [
        (
            "SECRET_BLOCK",
            [
                r"sk-[a-zA-Z0-9]{20,}",
                r"api[_-]?key\s*[:=]",
                r"private[_-]?key",
                r"-----BEGIN",
                r"AKIA[0-9A-Z]{16}",
            ],
        ),
        (
            "ACCOUNT_DATA_BLOCK",
            [
                r"balance\s*[:=]\s*\d+",
                r"position\s*[:=]\s*\d+",
                r"account\s*id",
                r"portfolio\s*value",
            ],
        ),
        (
            "ORDER_INSTRUCTION_BLOCK",
            [
                r"submit\s+(?:a\s+)?(?:buy|sell|order)",
                r"create_order",
                r"market\s+order",
                r"place\s+order",
                r"order\s+endpoint",
            ],
        ),
        (
            "FIREWALL_BYPASS_BLOCK",
            [
                r"bypass\s+(?:the\s+)?firewall",
                r"disable\s+(?:the\s+)?firewall",
                r"ignore\s+(?:the\s+)?firewall",
                r"skip\s+(?:the\s+)?firewall",
            ],
        ),
        (
            "CAP_MODIFICATION_BLOCK",
            [
                r"caps\.json",
                r"max_single_order",
                r"increase\s+(?:cap|limit|exposure)",
            ],
        ),
        (
            "LIVE_SUBMIT_MODIFICATION_BLOCK",
            [
                r"live_submit\.json",
                r"enable\s+live\s+submit",
                r"set\s+live_submit\s+enabled\s*:?\s*true",
                r"set\s+enabled\s*:?\s*true",
            ],
        ),
    ]

    _SECRET_LIKE_PATTERNS: list[str] = [
        r"sk-[a-zA-Z0-9]{20,}",
        r"[a-fA-F0-9]{40,}",
        r"[A-Za-z0-9+/]{40,}={0,2}",
        r"-----BEGIN[^-]+-----[\s\S]*?-----END[^-]+-----",
    ]

    def block_check(self, prompt: str) -> FirewallDecision:
        text = prompt.lower()
        for classification, patterns in self._PATTERNS:
            matched: list[str] = []
            for pat in patterns:
                for m in re.finditer(pat, text, re.IGNORECASE):
                    matched.append(m.group(0))
            if matched:
                return FirewallDecision(classification, False, matched)
        return FirewallDecision("SAFE_SANITIZED_MARKET_PROMPT", True, [])

    def sanitize(self, prompt: str) -> str:
        # First redact any secret values loaded from the environment.
        redacted = redact_text(prompt)
        # Then redact credential-like strings by shape.
        for pattern in self._SECRET_LIKE_PATTERNS:
            redacted = re.sub(pattern, "[REDACTED]", redacted, flags=re.IGNORECASE)
        redacted = redacted.replace("\x00", "")
        redacted = re.sub(r"\s+", " ", redacted).strip()
        return redacted[:16000]
