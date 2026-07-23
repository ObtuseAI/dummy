"""Strategy Claim Compiler: extraction, falsifiability, interpretations, registry."""
from __future__ import annotations

from datetime import datetime, timezone

from autonomy.strategy_claim_compiler import (
    assess_falsifiability,
    compile_claim,
    faithful_interpretations,
    heuristic_extract,
    mark_reproduced,
    record_claim,
)

NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)


def test_extract_concrete_crypto_claim():
    text = "Go long BTC on a 4h breakout, enter when RSI crosses 30, take profit at +5%."
    claim = heuristic_extract(text, source="reddit")
    # mean-reversion (RSI) takes precedence in the direction heuristic.
    assert claim.direction == "mean_reversion"
    assert claim.vertical == "crypto"
    assert claim.timeframe == "4h"
    assert claim.has_entry_rule and claim.has_exit_rule
    assert "entry_rule" not in claim.unspecified_fields


def test_extract_marks_unspecified_fields():
    claim = heuristic_extract("This strategy prints money.", source="tweet")
    assert claim.direction is None and claim.vertical is None
    assert set(claim.unspecified_fields) >= {
        "direction", "vertical", "timeframe", "entry_rule",
    }


def test_unfalsifiable_claim_is_rejected():
    claim = heuristic_extract("Trust me, it always wins.", source="tweet")
    verdict = assess_falsifiability(claim)
    assert verdict["falsifiable"] is False
    assert verdict["verdict"] == "REJECTED_UNFALSIFIABLE"
    assert "no_direction" in verdict["blockers"]
    # No interpretations generated for an untestable claim.
    compiled = compile_claim("Trust me, it always wins.", source="tweet", now=NOW)
    assert compiled["interpretations"] == []


def test_falsifiable_claim_enumerates_interpretations():
    text = "Short NFL home favorites; entry when the line moves against them."
    claim = heuristic_extract(text, source="reddit")
    assert assess_falsifiability(claim)["falsifiable"] is True
    interps = faithful_interpretations(claim)
    # Unspecified timeframe (2) x unspecified sizing (2) = 4 concrete strategies.
    assert len(interps) == 4
    assert all(i["direction"] == "short" and i["vertical"] == "sports" for i in interps)


def test_compile_and_record_roundtrip(tmp_path):
    text = "Long ETH momentum on the 1d, enter on breakout, exit on stop loss, risk 1 unit."
    compiled = compile_claim(text, source="reddit", now=NOW)
    assert compiled["falsifiability"]["falsifiable"] is True
    assert compiled["interpretation_count"] >= 1
    assert compiled["claim"]["extracted_at"] == NOW.isoformat()

    path = tmp_path / "claims.json"
    doc = record_claim(compiled, path=path)
    cid = compiled["claim"]["claim_id"]
    assert cid in doc["claims"]
    # Idempotent: re-recording does not duplicate.
    doc2 = record_claim(compiled, path=path)
    assert list(doc2["claims"]) == [cid]

    # Reproducibility outcome can be stamped later.
    assert mark_reproduced(cid, reproduced=False, path=path) is True
    import json
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["claims"][cid]["reproducibility"]["status"] == "FAILED_TO_REPRODUCE"
    assert mark_reproduced("nope", reproduced=True, path=path) is False


def test_injected_extractor_is_used():
    sentinel = heuristic_extract("Long BTC 1h entry breakout exit tp risk 1u", source="x")
    compiled = compile_claim(
        "ignored", source="x", now=NOW, extractor=lambda t, s: sentinel,
    )
    assert compiled["claim"]["direction"] == sentinel.direction
    assert compiled["claim"]["vertical"] == "crypto"
