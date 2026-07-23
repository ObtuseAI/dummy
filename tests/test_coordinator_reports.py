"""Wave-75 coordinator translations: top-threat decomposition + matchup lens."""
from __future__ import annotations

import json

from autonomy.matchup_lens import (
    build_matchup_report,
    grade_matchup,
    market_softness,
    source_strength,
)
from autonomy.top_threat import build_top_threat


# ---------------------------------------------------------------- top threat

class _Ledger:
    def __init__(self, rows):
        self._rows = rows

    def open_decisions(self, scope):
        assert scope == "shadow"
        return self._rows


def _position(ticker, price, filled, reserved=None):
    return {
        "market_ticker": ticker, "price_cents": price,
        "filled_count": filled, "reserved_count": reserved or filled,
    }


def test_top_threat_ranks_clusters_and_flags_concentration():
    rows = [
        # One game cluster carrying two sides = the dominant threat.
        _position("KXMLBGAME-26JUL23AZSTL-AZ", 60, 5),
        _position("KXMLBSPREAD-26JUL23AZSTL-AZ2", 40, 5),
        # A small unrelated crypto position.
        _position("KXBTC1H-26JUL231500-15", 50, 1),
    ]
    report = build_top_threat(_Ledger(rows))
    assert report["open_positions"] == 3
    assert report["book_worst_case_cents"] == 60 * 5 + 40 * 5 + 50
    top = report["top_threat"]
    assert "AZSTL" in top["cluster"]
    assert top["worst_case_cents"] == 500
    assert top["share_of_book"] > 0.35
    assert "single_cluster_concentration" in report["warnings"]
    assert report["by_subject"].get("mlb") == 500


def test_top_threat_empty_book_is_calm():
    report = build_top_threat(_Ledger([]))
    assert report["book_worst_case_cents"] == 0
    assert report["top_threat"] is None
    assert report["warnings"] == []


# ------------------------------------------------------------- matchup lens

def test_source_strength_matches_scope_hint():
    weights = {"market_debias|mlb|na|pre": 1.4, "sports_elo@sports": 0.8}
    assert source_strength(weights, "mlb") == 1.4
    assert source_strength(weights, "nhl") == 1.0   # neutral fallback


def test_market_softness_and_grades():
    soft = market_softness({
        "yes_bid": 40, "yes_ask": 50,               # 10c spread -> soft
        "selected_bid_size_fp": 5.0, "selected_ask_size_fp": 8.0,  # thin
        "quote_age_seconds": 400.0,
    })
    assert soft["softness"] is not None and soft["softness"] > 0.7
    firm = market_softness({
        "yes_bid": 49, "yes_ask": 50,
        "selected_bid_size_fp": 500.0, "selected_ask_size_fp": 400.0,
        "quote_age_seconds": 5.0,
    })
    assert firm["softness"] < 0.3
    assert grade_matchup(1.3, soft["softness"]) == "prime_isolation"
    assert grade_matchup(0.7, firm["softness"]) == "bait_suspect"
    assert grade_matchup(1.2, firm["softness"]) == "firm_market_edge"
    assert grade_matchup(1.2, None) == "unassessed"


def test_matchup_report_orders_prime_before_bait(tmp_path):
    board = tmp_path / "bet_board.json"
    recal = tmp_path / "last_recalibration.json"
    board.write_text(json.dumps({
        "generated_at": "2026-07-23T00:00:00+00:00",
        "top": [
            {"ticker": "SOFT-1", "label": "soft spot", "tier": "C",
             "after_fee_edge": 0.02, "league": "mlb",
             "yes_bid": 40, "yes_ask": 50,
             "selected_bid_size_fp": 5.0, "selected_ask_size_fp": 6.0,
             "quote_age_seconds": 400.0},
            {"ticker": "FIRM-1", "label": "firm spot", "tier": "B",
             "after_fee_edge": 0.05, "league": "nhl",
             "yes_bid": 49, "yes_ask": 50,
             "selected_bid_size_fp": 500.0, "selected_ask_size_fp": 600.0,
             "quote_age_seconds": 5.0},
            {"ticker": "WATCH-1", "tier": None, "after_fee_edge": 0.001},
        ],
    }), encoding="utf-8")
    recal.write_text(json.dumps({
        "weights": {"market_debias|mlb|na|pre": 1.5, "nhl_model@sports": 0.6},
    }), encoding="utf-8")

    report = build_matchup_report(board_path=board, recal_path=recal)
    assert [g["ticker"] for g in report["graded"]][:1] == ["SOFT-1"]
    assert report["graded"][0]["matchup"] == "prime_isolation"
    assert "FIRM-1" in report["bait_suspects"]
    # Non-tier rows never graded.
    assert all(g["ticker"] != "WATCH-1" for g in report["graded"])
