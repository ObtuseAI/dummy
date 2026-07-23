"""Security-inspection gate for harvested third-party repository code.

The existing source scanner categorizes files for relevance. This gate answers
a different question before any harvested code is adopted: does it exhibit
credential-harvesting or remote-code-execution red flags? A commenter on the
r/ai_trading Forven thread (and common sense) flagged that borrowing trading
repos without inspecting secret access, outbound traffic, install scripts, and
dynamic execution is how credentials get stolen.

The gate is static, fail-closed, and conservative:
  * BLOCK  -- credential exfiltration (secret access AND outbound network in
    one file) or obfuscated dynamic execution (eval/exec of decoded/fetched
    content). Never adopt.
  * REVIEW -- install-time side effects, bare dynamic execution, or a
    hardcoded exfiltration-style endpoint. Human inspection required.
  * SAFE   -- none of the above matched.

It inspects TEXT ONLY and never executes anything.
"""
from __future__ import annotations

import re
from typing import Any

# Secret access: reading credentials/keys/wallets.
_SECRET_ACCESS = re.compile(
    r"private[_-]?key|secret[_-]?key|api[_-]?secret|mnemonic|seed[_-]?phrase|"
    r"os\.environ|getenv|\.env\b|keyring|load_dotenv|aws_secret|"
    r"wallet\.privateKey|signing[_-]?key",
    re.IGNORECASE,
)
# Outbound network: sending data somewhere.
_OUTBOUND_NETWORK = re.compile(
    r"requests\.(post|put|get)|httpx\.|urllib\.request|aiohttp|socket\.|"
    r"smtplib|telegram|discord.*webhook|webhook|http[s]?://",
    re.IGNORECASE,
)
# Dynamic execution of content.
_DYNAMIC_EXEC = re.compile(r"\beval\s*\(|\bexec\s*\(|compile\s*\(|marshal\.loads|pickle\.loads")
# Decode/obfuscation tokens; combined with dynamic exec anywhere in the file
# this is the classic dropper shape (order-independent: exec(b64decode(...))
# and blob=b64decode(...); exec(blob) both match by co-occurrence).
_OBFUSCATION = re.compile(
    r"b64decode|base64\.|codecs\.decode|bytes\.fromhex|\.decode\(['\"]hex",
    re.IGNORECASE,
)


def _is_obfuscated_exec(text: str) -> bool:
    return bool(_OBFUSCATION.search(text)) and bool(_DYNAMIC_EXEC.search(text))
# Install-time side effects (setup.py / install hooks running commands).
_INSTALL_SIDE_EFFECT = re.compile(
    r"subprocess\.|os\.system|os\.popen|check_output|Popen|cmdclass|"
    r"install_requires.*http",
    re.IGNORECASE,
)
# Exfiltration-style endpoints often used to receive stolen data.
_EXFIL_ENDPOINT = re.compile(
    r"pastebin\.com|hastebin|discord(app)?\.com/api/webhooks|"
    r"t\.me/|api\.telegram\.org|transfer\.sh|\b\d{1,3}(\.\d{1,3}){3}\b",
    re.IGNORECASE,
)
_INSTALL_FILE = re.compile(r"(^|/)(setup\.py|setup\.cfg|conftest\.py|__init__\.py|install\.\w+)$")


def scan_file_security(path: str, text: str) -> list[dict[str, Any]]:
    """Return this file's security findings (severity + reason)."""
    findings: list[dict[str, Any]] = []
    secret = bool(_SECRET_ACCESS.search(text))
    outbound = bool(_OUTBOUND_NETWORK.search(text))
    obfuscated = _is_obfuscated_exec(text)

    if obfuscated:
        findings.append({"path": path, "severity": "block",
                         "category": "obfuscated_dynamic_execution"})
    if secret and outbound:
        findings.append({"path": path, "severity": "block",
                         "category": "credential_exfiltration"})
    if _EXFIL_ENDPOINT.search(text) and (secret or outbound):
        findings.append({"path": path, "severity": "block",
                         "category": "exfiltration_endpoint"})
    if _DYNAMIC_EXEC.search(text) and not obfuscated:
        findings.append({"path": path, "severity": "review",
                         "category": "dynamic_execution"})
    if _INSTALL_FILE.search(path) and _INSTALL_SIDE_EFFECT.search(text):
        findings.append({"path": path, "severity": "review",
                         "category": "install_time_side_effect"})
    return findings


def assess_repo_security(files: dict[str, str]) -> dict[str, Any]:
    """Aggregate a security verdict over a repo's {path: text} file map."""
    findings: list[dict[str, Any]] = []
    for path, text in (files or {}).items():
        if not isinstance(text, str):
            continue
        findings.extend(scan_file_security(str(path), text))
    has_block = any(f["severity"] == "block" for f in findings)
    has_review = any(f["severity"] == "review" for f in findings)
    verdict = "BLOCK" if has_block else ("REVIEW" if has_review else "SAFE")
    return {
        "gate_version": "repo_security_gate_v1",
        "verdict": verdict,
        "adoptable_without_human_review": verdict == "SAFE",
        "block_reasons": sorted({f["category"] for f in findings if f["severity"] == "block"}),
        "review_reasons": sorted({f["category"] for f in findings if f["severity"] == "review"}),
        "findings": findings,
        "files_scanned": len(files or {}),
    }
