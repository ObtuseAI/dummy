"""WS-13: council snapshot writer -- pure assembly, no I/O."""
from __future__ import annotations

from autonomy.council_snapshot import build_council_snapshot


class _FakeRegistry:
    def __init__(self, report):
        self._report = report

    def health_report(self):
        return self._report


def test_build_council_snapshot_tags_open_opportunities_per_specialist():
    council = _FakeRegistry([
        {"name": "mlb", "status": "ok", "details": {"games_seen": 42}},
        {"name": "nba", "status": "dormant", "details": {"in_season": False}},
        {"name": "crypto", "status": "ok", "details": {"has_champion": True}},
    ])
    report = {
        "opportunities": [
            {"ticker": "KXMLBGAME-1", "side": "YES"},
            {"ticker": "KXMLBGAME-2", "side": "NO"},
            {"ticker": "KXBTCD-1", "side": "YES"},
        ],
    }
    ticker_specialist = {
        "KXMLBGAME-1": "mlb",
        "KXMLBGAME-2": "mlb",
        "KXBTCD-1": "crypto",
    }
    snapshot = build_council_snapshot(council, report, ticker_specialist, now_iso="2026-07-13T00:00:00Z")
    assert snapshot["generated_at"] == "2026-07-13T00:00:00Z"
    by_name = {row["name"]: row for row in snapshot["specialists"]}
    assert by_name["mlb"]["open_opportunities"] == 2
    assert by_name["mlb"]["status"] == "ok"
    assert by_name["mlb"]["details"]["games_seen"] == 42
    assert by_name["crypto"]["open_opportunities"] == 1
    assert by_name["nba"]["open_opportunities"] == 0  # no ticker attributed to nba


def test_build_council_snapshot_untagged_ticker_counts_toward_nobody():
    council = _FakeRegistry([{"name": "mlb", "status": "ok", "details": {}}])
    report = {"opportunities": [{"ticker": "KXWNBA-1", "side": "YES"}]}
    # WNBA has no specialist (routes through the sportsbook-consensus
    # fallback, per autonomy/specialists/factory.py), so the ticker is
    # either absent from the map or maps to None -- either way it must not
    # be attributed to "mlb" or blow up the assembly.
    snapshot = build_council_snapshot(council, report, {}, now_iso="t1")
    assert snapshot["specialists"][0]["open_opportunities"] == 0


def test_build_council_snapshot_empty_opportunities_is_zero_everywhere():
    council = _FakeRegistry([
        {"name": "mlb", "status": "cold", "details": {}},
    ])
    snapshot = build_council_snapshot(council, {}, {}, now_iso="t1")
    assert snapshot["specialists"][0]["open_opportunities"] == 0
    assert snapshot["specialists"][0]["status"] == "cold"


def test_build_council_snapshot_survives_a_degraded_specialist_entry():
    # health_report() itself is already exception-guarded (base.py); this
    # confirms the writer doesn't require a well-formed "details" dict.
    council = _FakeRegistry([
        {"name": "nhl", "status": "degraded", "details": {"error": "ValueError"}},
    ])
    snapshot = build_council_snapshot(council, {}, {}, now_iso="t1")
    assert snapshot["specialists"] == [
        {"name": "nhl", "status": "degraded", "details": {"error": "ValueError"},
         "open_opportunities": 0},
    ]
