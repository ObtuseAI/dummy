"""Strategy Claim Compiler: extraction, falsifiability, interpretations, registry."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from autonomy import strategy_claim_compiler
from autonomy.strategy_claim_compiler import (
    PIPELINE_STATUS,
    assess_falsifiability,
    compile_claim,
    faithful_interpretations,
    heuristic_extract,
    mark_reproduced,
    record_claim,
    registry_status,
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


# --- Wave-84: the compiler is unwired and must say so -----------------------


def test_compiled_claim_declares_it_is_unwired():
    compiled = compile_claim(
        "Long BTC 1h, enter on breakout, take profit +5%.", source="reddit", now=NOW,
    )

    # Falsifiable, and still not evidence of anything.
    assert compiled["falsifiability"]["verdict"] == "TESTABLE"
    assert compiled["pipeline_status"] == "UNWIRED_NO_AUTOMATED_CONSUMER"
    assert compiled["wired_into_production"] is False
    assert compiled["wired_into_strategy_miner"] is False
    assert compiled["reproducibility"]["backtested"] is False
    assert compiled["reproducibility"]["automated_backtest_consumer"] is None
    assert compiled["authority"] == "research_spec_only_no_execution"


def test_recorded_registry_header_declares_no_consumer(tmp_path):
    path = tmp_path / "claims.json"
    compiled = compile_claim(
        "Short NFL favorites, entry when the line moves.", source="reddit", now=NOW,
    )

    document = record_claim(compiled, path=path)

    assert document["registry_status"] == PIPELINE_STATUS
    assert document["wired_into_production"] is False
    assert document["wired_into_strategy_miner"] is False
    assert document["automated_backtest_consumer"] is None
    assert document["claim_count"] == 1
    assert document["reproduced_claim_count"] == 0
    assert document["updated_at"]
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["registry_status"] == PIPELINE_STATUS


def test_manual_reproduction_stamp_is_labelled_as_manual(tmp_path):
    path = tmp_path / "claims.json"
    compiled = compile_claim(
        "Long ETH 1d, enter on breakout, exit on stop loss.", source="x", now=NOW,
    )
    record_claim(compiled, path=path)
    claim_id = compiled["claim"]["claim_id"]

    assert mark_reproduced(claim_id, reproduced=True, path=path) is True

    stored = json.loads(path.read_text(encoding="utf-8"))
    entry = stored["claims"][claim_id]["reproducibility"]
    assert entry["status"] == "REPRODUCED"
    assert entry["recorded_by"] == "manual_operator_entry_not_an_automated_backtest"
    assert stored["reproduced_claim_count"] == 1
    # Recording an outcome does not make the pipeline live.
    assert stored["registry_status"] == PIPELINE_STATUS


def test_registry_status_reports_a_missing_registry_honestly(tmp_path):
    missing = tmp_path / "never_written.json"

    status = registry_status(missing)

    assert status["registry_exists"] is False
    assert status["registry_readable"] is False
    assert status["claim_count"] == 0
    assert status["registry_status"] == PIPELINE_STATUS
    assert "claims" not in status


def test_no_production_module_imports_the_compiler():
    """The deprecation is only true while nothing wires it in."""
    root = Path(strategy_claim_compiler.__file__).resolve().parents[1]
    skip_parts = {
        ".git", ".venv", "__pycache__", "tests", "archive", "scripts",
        "node_modules", "runtime", "artifacts",
    }
    importers = []
    for path in root.rglob("*.py"):
        if skip_parts & set(path.parts):
            continue
        if path.resolve() == Path(strategy_claim_compiler.__file__).resolve():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "strategy_claim_compiler" in text:
            importers.append(str(path.relative_to(root)))

    assert importers == [], (
        "strategy_claim_compiler is documented as unwired; these modules now "
        f"import it and the docstring/status fields must be corrected: {importers}"
    )


def test_injected_extractor_is_used():
    sentinel = heuristic_extract("Long BTC 1h entry breakout exit tp risk 1u", source="x")
    compiled = compile_claim(
        "ignored", source="x", now=NOW, extractor=lambda t, s: sentinel,
    )
    assert compiled["claim"]["direction"] == sentinel.direction
    assert compiled["claim"]["vertical"] == "crypto"
