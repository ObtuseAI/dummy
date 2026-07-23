"""Strategy Claim Compiler: turn an unstructured strategy claim into a testable spec.

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
        "compiler_version": "strategy_claim_compiler_v1",
        "claim": claim.to_dict(),
        "falsifiability": falsifiability,
        "interpretations": interpretations,
        "interpretation_count": len(interpretations),
        "reproducibility": {
            "status": "NOT_YET_BACKTESTED",
            "note": (
                "backtest each interpretation on point-in-time data, stress "
                "costs/latency, compare vs a market baseline, then record "
                "whether the original claim reproduced"
            ),
        },
        "authority": "research_spec_only_no_execution",
    }


def record_claim(
    compiled: dict[str, Any], *, path: Path | str = CLAIMS_REGISTRY_PATH,
) -> dict[str, Any]:
    """Append a compiled claim to the registry (idempotent by claim_id)."""
    target = Path(path)
    document: dict[str, Any] = {"schema_version": 1, "claims": {}}
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
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(document, stream, indent=2, sort_keys=True)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return document


def mark_reproduced(
    claim_id: str,
    *,
    reproduced: bool,
    evidence: dict[str, Any] | None = None,
    path: Path | str = CLAIMS_REGISTRY_PATH,
) -> bool:
    """Record a backtest outcome against a stored claim; True if updated."""
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
        "evidence": evidence or {},
    }
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(target)
    return True
