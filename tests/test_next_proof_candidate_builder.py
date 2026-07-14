

from core.kalshi_market_validator import MarketMetadata, ContractMetadata
from core.proof_order_candidate import (
    build_validated_proof_candidate,
    write_candidate_packet,
    safe_preview,
)


def test_builder_prefers_smallest_proof_size():
    metadata = MarketMetadata(
        ticker="KXBTC-26DEC25000-C",
        status="open",
        open_time=None,
        close_time=None,
        trading_allowed=True,
        min_price_cents=1,
        max_price_cents=99,
        tick_size_cents=1,
        contracts=[ContractMetadata(ticker="KXBTC-26DEC25000-C", status="open", tradable=True)],
    )
    caps = {"max_order_count": 1, "max_single_order_cents": 100}
    context = {
        "descriptor_hash": "9A3A...3508",
        "caps_hash": "F7D9...E5B5",
        "live_submit_hash": "3875...515E",
        "evidence_registry_hash": "1C89...0113",
        "previous_real_broker_attempt_status": "BROKER_REJECTED",
    }
    candidate = build_validated_proof_candidate(metadata, caps, context)
    assert candidate.order_type == "LIMIT"
    assert candidate.count == 1
    assert candidate.price == 1
    assert candidate.submit_allowed_now is False
    assert candidate.requires_new_operator_proof_authority is True


def test_candidate_packet_has_no_secrets(tmp_path):
    metadata = MarketMetadata(
        ticker="KXBTC-26DEC25000-C",
        status="open",
        open_time=None,
        close_time=None,
        trading_allowed=True,
        min_price_cents=1,
        max_price_cents=99,
        tick_size_cents=1,
        contracts=[ContractMetadata(ticker="KXBTC-26DEC25000-C", status="open", tradable=True)],
    )
    caps = {"max_order_count": 1}
    context = {"previous_real_broker_attempt_status": "BROKER_REJECTED"}
    candidate = build_validated_proof_candidate(metadata, caps, context)
    path = tmp_path / "VALIDATED_KALSHI_PROOF_CANDIDATE.json"
    write_candidate_packet(candidate, path)
    raw = path.read_text()
    assert "idempotency" not in raw.lower() or "redacted" in raw.lower()
    assert "private" not in raw.lower()
    # `secrets_redacted` is a safe metadata flag, not a leaked secret value.
    assert "secret" not in raw.lower().replace("\"secrets_redacted\": true", "")


def test_safe_preview_omits_sensitive_fields():
    metadata = MarketMetadata(
        ticker="KXBTC-26DEC25000-C",
        status="open",
        open_time=None,
        close_time=None,
        trading_allowed=True,
        min_price_cents=1,
        max_price_cents=99,
        tick_size_cents=1,
        contracts=[ContractMetadata(ticker="KXBTC-26DEC25000-C", status="open", tradable=True)],
    )
    candidate = build_validated_proof_candidate(metadata, {}, {})
    preview = safe_preview(candidate)
    assert "idempotency" not in preview
    assert preview["submit_allowed_now"] is False
