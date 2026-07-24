"""Strategy Claim Compiler: turn an unstructured strategy claim into a testable spec.

NOT WIRED -- RESEARCH TOOL, NOT A PRODUCTION CAPABILITY (2026-07-24 audit, s6)
=============================================================================
Nothing in production calls this module. It has no scheduled task, no caller
inside the cycle, and no automated backtest consumes its output:

* ``compile_claim`` runs only when an operator runs
  ``scripts/run_dummy_strategy_claim.py`` by hand;
* the registry at ``runtime/autonomy/strategy_claims.json`` is written only by
  that manual path (as of this writing the file does not exist and zero claims
  have ever been recorded);
* ``mark_reproduced`` has no production caller -- a claim's reproducibility
  status can only change if a human runs a backtest and records the outcome;
* a TESTABLE verdict therefore means "this claim COULD be tested", never
  "this claim was tested" and never "this claim works".

It was deliberately left unwired rather than connected to
``autonomy/strategy_miner.py``: the miner's hypothesis space is numeric
predicates (``feature <= threshold``) over Dummy's own settled, market-
benchmarked ledger emissions, with thresholds fit on its TRAIN split. A
compiled claim's interpretations are prose-level ("entry as stated on the 1h,
flat 1u"), and Dummy has no ledger rows for a strategy it never ran, so
feeding them to the miner would require inventing new evidence semantics and
enlarging the miner's FDR family -- which would silently move every existing
mined verdict. Anything that reads this module's output as live capability is
reading it wrong.

Reddit posts, YouTube transcripts, tweets, and repo READMEs assert trading
strategies in prose. This compiler formalizes such a claim into a structured,
falsifiable specification so Dummy can (later) backtest it rather than trust it:

  1. extract direction, market/vertical, timeframe, entry/exit hints, sizing;
  2. mark every unspecified field explicitly;
  3. reject claims that cannot be falsified (no testable entry OR no market OR
     no direction -> UNFALSIFIABLE, never "tested");
  4. enumerate a bounded set of faithful interpretations for the unspecified
     fields, so a single vague claim is tested as several concrete strategies;
  5. record the claim + its reproducibility outcome in a registry.

The default extractor is keyless and deterministic (heuristics over the text),
so this works with no model call; an LLM extractor can be injected for richer
parsing. Nothing here trades or grants authority -- it produces a research spec
and a reproducibility verdict.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

CLAIMS_REGISTRY_PATH = Path("runtime/autonomy/strategy_claims.json")

# Deprecation / wiring status. Stamped into every compiled claim and into the
# registry header so a reader of the artifact -- not just a reader of this
# file -- can see that nothing consumes it.
PIPELINE_STATUS = "UNWIRED_NO_AUTOMATED_CONSUMER"
PIPELINE_STATUS_DETAIL = (
    "research tool only: no scheduled task, no production caller, and no "
    "automated backtest consumes compiled interpretations. A TESTABLE verdict "
    "means the claim could be tested, not that it was tested."
)
COMPILER_VERSION = "strategy_claim_compiler_v1"
CLAIMS_REGISTRY_SCHEMA_VERSION = 1

_DIRECTION_LONG = re.compile(r"\b(long|buy|bullish|breakout|momentum up|go long)\b", re.IGNORECASE)
_DIRECTION_SHORT = re.compile(r"\b(short|sell|bearish|breakdown|fade|go short)\b", re.IGNORECASE)
_MEAN_REVERSION = re.compile(r"\b(mean[- ]?revert|revert|oversold|overbought|rsi)\b", re.IGNORECASE)

_VERTICAL_CRYPTO = re.compile(r"\b(btc|eth|sol|bitcoin|ethereum|solana|crypto|perp|funding)\b", re.IGNORECASE)
_VERTICAL_SPORTS = re.compile(r"\b(nba|nfl|mlb|nhl|wnba|ncaa|moneyline|spread|over/under|parlay|prop)\b", re.IGNORECASE)

_TIMEFRAME = re.compile(
    r"\b(\d+)\s*(min(?:ute)?s?|m|h(?:our)?s?|d(?:ay)?s?|w(?:eek)?s?)\b", re.IGNORECASE
)
_ENTRY = re.compile(r"\b(enter|entry|buy when|go long when|signal when|trigger)\b", re.IGNORECASE)
_EXIT = re.compile(r"\b(exit|take profit|stop loss|close when|target|tp|sl)\b", re.IGNORECASE)
_SIZING = re.compile(r"\b(kelly|fixed|flat|percent of|% of|risk \d|units?)\b", re.IGNORECASE)


@dataclass(frozen=True)
class StrategyClaim:
    """A structured, falsifiable strategy specification extracted from text."""

    claim_id: str
    source: str
    direction: str | None            # "long" | "short" | "mean_reversion" | None
    vertical: str | None             # "crypto" | "sports" | None
    timeframe: str | None            # normalized e.g. "1h", "1d", or None
    has_entry_rule: bool
    has_exit_rule: bool
    has_sizing_rule: bool
    unspecified_fields: tuple[str, ...]
    raw_excerpt: str
    extracted_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "source": self.source,
            "direction": self.direction,
            "vertical": self.vertical,
            "timeframe": self.timeframe,
            "has_entry_rule": self.has_entry_rule,
            "has_exit_rule": self.has_exit_rule,
            "has_sizing_rule": self.has_sizing_rule,
            "unspecified_fields": list(self.unspecified_fields),
            "raw_excerpt": self.raw_excerpt,
            "extracted_at": self.extracted_at,
        }


def _normalize_timeframe(text: str) -> str | None:
    match = _TIMEFRAME.search(text)
    if not match:
        return None
    n, unit = match.group(1), match.group(2).lower()
    if unit.startswith("m") and unit != "m" or unit in ("min", "mins", "minute", "minutes"):
        return f"{n}m"
    if unit == "m":
        return f"{n}m"
    if unit.startswith("h"):
        return f"{n}h"
    if unit.startswith("d"):
        return f"{n}d"
    if unit.startswith("w"):
        return f"{n}w"
    return None


def heuristic_extract(text: str, *, source: str) -> StrategyClaim:
    """Keyless deterministic extraction of a strategy claim from prose."""
    body = str(text or "")
    if _MEAN_REVERSION.search(body):
        direction: str | None = "mean_reversion"
    elif _DIRECTION_LONG.search(body):
        direction = "long"
    elif _DIRECTION_SHORT.search(body):
        direction = "short"
    else:
        direction = None
    if _VERTICAL_CRYPTO.search(body):
        vertical: str | None = "crypto"
    elif _VERTICAL_SPORTS.search(body):
        vertical = "sports"
    else:
        vertical = None
    timeframe = _normalize_timeframe(body)
    has_entry = bool(_ENTRY.search(body))
    has_exit = bool(_EXIT.search(body))
    has_sizing = bool(_SIZING.search(body))

    unspecified = []
    if direction is None:
        unspecified.append("direction")
    if vertical is None:
        unspecified.append("vertical")
    if timeframe is None:
        unspecified.append("timeframe")
    if not has_entry:
        unspecified.append("entry_rule")
    if not has_exit:
        unspecified.append("exit_rule")
    if not has_sizing:
        unspecified.append("sizing_rule")

    excerpt = body.strip().replace("\n", " ")[:280]
    claim_id = "claim-" + hashlib.sha256(f"{source}:{body}".encode()).hexdigest()[:12]
    return StrategyClaim(
        claim_id=claim_id, source=source, direction=direction, vertical=vertical,
        timeframe=timeframe, has_entry_rule=has_entry, has_exit_rule=has_exit,
        has_sizing_rule=has_sizing, unspecified_fields=tuple(unspecified),
        raw_excerpt=excerpt,
        extracted_at="",  # stamped by compile_claim (deterministic input elsewhere)
    )


def assess_falsifiability(claim: StrategyClaim) -> dict[str, Any]:
    """A claim is falsifiable only with a testable entry, a market, and a direction.

    Without these it is a vibe, not a strategy: it can never be turned into a
    concrete backtest whose failure would refute it.
    """
    blockers = []
    if claim.direction is None:
        blockers.append("no_direction")
    if claim.vertical is None:
        blockers.append("no_market_or_vertical")
    if not claim.has_entry_rule:
        blockers.append("no_entry_condition")
    falsifiable = not blockers
    return {
        "falsifiable": falsifiable,
        "verdict": "TESTABLE" if falsifiable else "REJECTED_UNFALSIFIABLE",
        "blockers": blockers,
    }


# Bounded interpretation grids for common unspecified fields, so one vague
# claim becomes several concrete strategies to test rather than a guess.
_TIMEFRAME_GRID = ("1h", "1d")
_SIZING_GRID = ("flat_1u", "fractional_kelly_0.25")


def faithful_interpretations(claim: StrategyClaim) -> list[dict[str, Any]]:
    """Enumerate concrete strategies covering the claim's unspecified fields."""
    timeframes = [claim.timeframe] if claim.timeframe else list(_TIMEFRAME_GRID)
    sizings = ["as_stated"] if claim.has_sizing_rule else list(_SIZING_GRID)
    interpretations = []
    for tf in timeframes:
        for sizing in sizings:
            interpretations.append({
                "direction": claim.direction,
                "vertical": claim.vertical,
                "timeframe": tf,
                "sizing": sizing,
                "entry_rule": "as_stated" if claim.has_entry_rule else "unspecified",
                "exit_rule": "as_stated" if claim.has_exit_rule else "hold_to_settlement",
            })
    return interpretations


def compile_claim(
    text: str,
    *,
    source: str,
    now: datetime | None = None,
    extractor: Callable[[str, str], StrategyClaim] | None = None,
) -> dict[str, Any]:
    """Compile prose into a structured, falsifiability-graded strategy spec."""
    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    extract = extractor or (lambda t, s: heuristic_extract(t, source=s))
    base = extract(text, source)
    from dataclasses import replace

    claim = replace(base, extracted_at=stamp)
    falsifiability = assess_falsifiability(claim)
    interpretations = (
        faithful_interpretations(claim) if falsifiability["falsifiable"] else []
    )
    return {
        "compiler_version": COMPILER_VERSION,
        "claim": claim.to_dict(),
        "falsifiability": falsifiability,
        "interpretations": interpretations,
        "interpretation_count": len(interpretations),
        "reproducibility": {
            "status": "NOT_YET_BACKTESTED",
            "backtested": False,
            "automated_backtest_consumer": None,
            "note": (
                "no automated consumer exists: this status can only change if "
                "a human backtests each interpretation on point-in-time data, "
                "stresses costs/latency, compares vs a market baseline, and "
                "records the outcome via mark_reproduced()"
            ),
        },
        "pipeline_status": PIPELINE_STATUS,
        "pipeline_status_detail": PIPELINE_STATUS_DETAIL,
        "wired_into_production": False,
        "wired_into_strategy_miner": False,
        "authority": "research_spec_only_no_execution",
    }


def _stamp_registry_status(
    document: dict[str, Any], *, now: datetime | None = None,
) -> dict[str, Any]:
    """Refresh the registry header so the artifact declares its own status."""
    claims = document.get("claims")
    claims = claims if isinstance(claims, dict) else {}
    reproduced = sum(
        1
        for claim in claims.values()
        if isinstance(claim, dict)
        and (claim.get("reproducibility") or {}).get("status") == "REPRODUCED"
    )
    document["schema_version"] = CLAIMS_REGISTRY_SCHEMA_VERSION
    document["registry_status"] = PIPELINE_STATUS
    document["registry_status_detail"] = PIPELINE_STATUS_DETAIL
    document["wired_into_production"] = False
    document["wired_into_strategy_miner"] = False
    document["automated_backtest_consumer"] = None
    document["written_by"] = "manual_operator_run_of_run_dummy_strategy_claim"
    document["claim_count"] = len(claims)
    document["reproduced_claim_count"] = reproduced
    document["updated_at"] = (
        now or datetime.now(timezone.utc)
    ).astimezone(timezone.utc).isoformat()
    return document


def _atomic_write_json(document: dict[str, Any], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(document, stream, indent=2, sort_keys=True)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def registry_status(path: Path | str = CLAIMS_REGISTRY_PATH) -> dict[str, Any]:
    """Report the registry's real state, including "it does not exist".

    Used by the manual runner so an operator is never left inferring capability
    from an absent file.
    """
    target = Path(path)
    document: dict[str, Any] = {"claims": {}}
    exists = target.exists()
    readable = False
    if exists:
        try:
            loaded = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            loaded = None
        if isinstance(loaded, dict) and isinstance(loaded.get("claims"), dict):
            document = loaded
            readable = True
    status = _stamp_registry_status(dict(document))
    status.pop("claims", None)
    status["registry_path"] = str(target)
    status["registry_exists"] = exists
    status["registry_readable"] = readable
    return status


def record_claim(
    compiled: dict[str, Any], *, path: Path | str = CLAIMS_REGISTRY_PATH,
) -> dict[str, Any]:
    """Append a compiled claim to the registry (idempotent by claim_id).

    Manual path only -- no production code calls this. The written document
    declares that, so the artifact cannot be mistaken for a live pipeline's
    output.
    """
    target = Path(path)
    document: dict[str, Any] = {
        "schema_version": CLAIMS_REGISTRY_SCHEMA_VERSION, "claims": {},
    }
    if target.exists():
        try:
            loaded = json.loads(target.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and isinstance(loaded.get("claims"), dict):
                document = loaded
        except (OSError, ValueError):
            pass
    claim_id = str(compiled.get("claim", {}).get("claim_id") or "")
    if claim_id and claim_id not in document["claims"]:
        document["claims"][claim_id] = compiled
    _stamp_registry_status(document)
    _atomic_write_json(document, target)
    return document


def mark_reproduced(
    claim_id: str,
    *,
    reproduced: bool,
    evidence: dict[str, Any] | None = None,
    path: Path | str = CLAIMS_REGISTRY_PATH,
) -> bool:
    """Record a backtest outcome against a stored claim; True if updated.

    MANUAL ENTRY POINT: nothing in production calls this. It exists so a human
    who has actually run a backtest can stamp the outcome; it never runs a
    backtest itself and never validates the evidence it is handed.
    """
    target = Path(path)
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    claim = (document.get("claims") or {}).get(claim_id)
    if not isinstance(claim, dict):
        return False
    claim["reproducibility"] = {
        "status": "REPRODUCED" if reproduced else "FAILED_TO_REPRODUCE",
        "backtested": True,
        "recorded_by": "manual_operator_entry_not_an_automated_backtest",
        "evidence": evidence or {},
    }
    _stamp_registry_status(document)
    _atomic_write_json(document, target)
    return True
