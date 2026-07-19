"""Wave-51: per-scope analytics + overview builder for the redesigned dashboard.

Pins the honest-accuracy contract: forecasts graded once per market (pick of
record), coins/leagues resolved correctly, and the overview account rendered as
the paper bankroll it is -- with the promotion ladder split into promoted vs
close-to-promotion.
"""
from __future__ import annotations

from datetime import datetime, timezone

from autonomy.ledger import AutonomyLedger
from autonomy.scope_analytics import (
    CRYPTO,
    SPORTS,
    build_overview,
    build_scope_analytics,
    scope_key,
)

NOW = datetime.now(timezone.utc)


def _iso(days_ago: float = 0.0) -> str:
    from datetime import timedelta
    return (NOW - timedelta(days=days_ago)).isoformat()


def _ledger(tmp_path) -> AutonomyLedger:
    return AutonomyLedger(db_path=tmp_path / "ledger.db")


def _add_decision(led, ticker, *, prob, side, result, action="BUY_YES",
                  market=None, ev=5.0, days_ago=1.0, decision_id=None, settle=True):
    conn = led._conn
    did = decision_id or f"{ticker}-{prob}-{days_ago}"
    conn.execute(
        "INSERT INTO decisions(decision_id,market_ticker,action,side,price_cents,count,"
        "ev_cents,kelly,notional_cents,probability_yes,market_implied_yes,sources_used,created_at)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (did, ticker, action, side, 50, 1, ev, 0.1, 100, prob, market, "[]", _iso(days_ago)),
    )
    if settle:
        conn.execute(
            "INSERT OR REPLACE INTO settlements(market_ticker,result_yes,settled_at) VALUES(?,?,?)",
            (ticker, 1 if result else 0, _iso(days_ago - 0.1)),
        )
    conn.commit()


# ---- scope_key -------------------------------------------------------------

def test_scope_key_resolves_coins_and_leagues():
    assert scope_key("KXBTCD-25JUL19") == (CRYPTO, "BTC")
    assert scope_key("KXETH-1H") == (CRYPTO, "ETH")
    assert scope_key("KXSOLE-X") == (CRYPTO, "SOL")
    # sports classify to the SPORTS vertical (league via the series registry)
    assert scope_key("KXMLBGAME-25JUL19DETCLE")[0] == SPORTS
    # non-crypto/sports fall to their vertical name, never dropped
    assert scope_key("KXCPI-25")[0] not in (CRYPTO, SPORTS)


# ---- scope analytics -------------------------------------------------------

def test_scope_summary_grades_forecasts_once_per_market(tmp_path):
    led = _ledger(tmp_path)
    # BTC: 3 markets, model calls 2 right, 1 wrong (directional).
    _add_decision(led, "KXBTCD-A", prob=0.8, side="YES", result=True)
    _add_decision(led, "KXBTCD-B", prob=0.7, side="YES", result=True)
    _add_decision(led, "KXBTCD-C", prob=0.6, side="YES", result=False)
    # A re-pricing of market A must NOT double-count: later, less confident.
    _add_decision(led, "KXBTCD-A", prob=0.55, side="YES", result=True,
                  days_ago=0.5, decision_id="KXBTCD-A-late")

    out = build_scope_analytics(led._conn)
    btc = out["verticals"][CRYPTO]["scopes"]["BTC"]["summary"]
    assert btc["n"] == 3                     # pick of record only -> 3 markets
    assert btc["hit_rate"] == round(2 / 3, 4)
    assert 0.0 < btc["brier"] < 1.0
    led.close()


def test_scope_edge_vs_market_and_progression(tmp_path):
    led = _ledger(tmp_path)
    for i in range(12):
        # model sharper than the market line on every settled market
        _add_decision(led, f"KXETH-{i}", prob=0.85 if i % 2 else 0.15,
                      side="YES", result=(i % 2 == 1), market=0.55 if i % 2 else 0.45,
                      days_ago=20 - i)
    eth = build_scope_analytics(led._conn)["verticals"][CRYPTO]["scopes"]["ETH"]
    assert eth["summary"]["brier_edge"] is not None
    assert eth["summary"]["brier_edge"] > 0          # model beats the line
    assert len(eth["progression"]) >= 2               # bucketed over time
    led.close()


def test_current_picks_are_unsettled_and_ranked(tmp_path):
    led = _ledger(tmp_path)
    # open (unsettled) BTC picks with different edges, plus a settled one to ignore
    _add_decision(led, "KXBTCD-OPEN1", prob=0.7, side="YES", result=False,
                  action="BUY_YES", ev=9.0, settle=False)
    _add_decision(led, "KXBTCD-OPEN2", prob=0.6, side="NO", result=False,
                  action="BUY_NO", ev=3.0, settle=False)
    _add_decision(led, "KXBTCD-DONE", prob=0.8, side="YES", result=True, ev=20.0)
    picks = build_scope_analytics(led._conn)["verticals"][CRYPTO]["scopes"]["BTC"]["picks"]
    tickers = [p["ticker"] for p in picks]
    assert "KXBTCD-DONE" not in tickers               # settled excluded
    assert tickers[0] == "KXBTCD-OPEN1"               # ranked by edge desc
    led.close()


def test_empty_ledger_is_safe(tmp_path):
    led = _ledger(tmp_path)
    out = build_scope_analytics(led._conn)
    assert out["verticals"] == {}
    ov = build_overview(led._conn, {})
    assert ov["bankroll_cents"] == 10_000            # falls back to base
    assert ov["promoted"] == [] and ov["close_to_promotion"] == []
    led.close()


# ---- overview --------------------------------------------------------------

def test_overview_paper_account_and_promotion_split(tmp_path):
    led = _ledger(tmp_path)
    conn = led._conn
    for i, (bank, exp) in enumerate([(10_000, 0), (9_800, 120), (9_500, 0)]):
        conn.execute(
            "INSERT INTO bankroll_curve(bankroll_cents,open_exposure_cents,stage,created_at)"
            " VALUES(?,?,?,?)", (bank, exp, 2, _iso(3 - i)))
    conn.commit()
    report = {
        "realized_decision_pnl_cents": -500,
        "realized_trade_statistics": {"net_pnl_cents": -500, "roi_on_entry_cost": -0.2,
                                       "win_rate": 0.33, "trades": 9, "profit_factor": 0.6,
                                       "max_drawdown_cents": 800},
        "derived_weights": {"market_prior": 2.1, "crypto_ewma": 0.9},
        "crypto_challenger_gates": {
            "promoted_one": {"auto_promote": True, "execution_authority": True,
                             "blockers": [], "evidence": {"contested_brier_advantage_lower95": 0.01,
                                                          "contested_markets": 200}},
            "near": {"auto_promote": False, "execution_authority": False,
                     "blockers": ["contested Brier advantage lower95 is not positive"],
                     "evidence": {"contested_brier_advantage_lower95": -0.005, "contested_markets": 150}},
            "far": {"auto_promote": False, "execution_authority": False,
                    "blockers": ["x"], "evidence": {"contested_brier_advantage_lower95": -0.04,
                                                     "contested_markets": 90}},
        },
    }
    ov = build_overview(conn, report)
    assert ov["paper"] is True
    assert ov["bankroll_cents"] == 9_500 and ov["base_bankroll_cents"] == 10_000
    assert ov["account_roi"] == round((9_500 - 10_000) / 10_000, 4)   # -0.05
    assert [p["name"] for p in ov["promoted"]] == ["promoted_one"]
    # close-to-promotion sorted nearest-first (least-negative lower95)
    assert [c["name"] for c in ov["close_to_promotion"]] == ["near", "far"]
    assert ov["active_sources"][0]["source"] == "market_prior"        # sorted by weight
    assert len(ov["balance_curve"]) == 3
    led.close()


# ---- endpoint wiring -------------------------------------------------------

def test_dashboard_serves_overview_and_scopes_from_snapshot(tmp_path, monkeypatch):
    import json

    from starlette.testclient import TestClient

    import autonomy.dashboard as dash

    (tmp_path / "latest_dashboard_snapshot.json").write_text(json.dumps({
        "generated_at": "2026-07-19T18:00:00+00:00",
        "backtest_generated_at": "2026-07-19T12:00:00+00:00",
        "overview": {"bankroll_cents": 9500, "paper": True},
        "scopes": {"verticals": {"CRYPTO": {"scopes": {"BTC": {"summary": {"n": 5}}}}}},
    }), encoding="utf-8")
    monkeypatch.setattr(dash, "RUNTIME_DIR", tmp_path)

    client = TestClient(dash.build_app())
    ov = client.get("/api/overview").json()
    assert ov["bankroll_cents"] == 9500 and ov["paper"] is True
    assert ov["generated_at"] == "2026-07-19T18:00:00+00:00"
    sc = client.get("/api/scopes").json()
    assert sc["verticals"]["CRYPTO"]["scopes"]["BTC"]["summary"]["n"] == 5


def test_dashboard_index_serves_redesigned_page():
    from starlette.testclient import TestClient

    import autonomy.dashboard as dash

    body = TestClient(dash.build_app()).get("/").text
    assert "totalizator" in body            # the redesigned shell
    assert "/api/overview" in body and "/api/scopes" in body


# ---- Wave-52: scope "other data" fold-in -----------------------------------

def _write(p, obj):
    import json
    p.write_text(json.dumps(obj), encoding="utf-8")


def test_scope_extras_folds_council_clv_mispricing_ejections(tmp_path):
    from autonomy.scope_analytics import build_scope_extras

    _write(tmp_path / "clv_report.json", {"scopes": {
        "crypto|ladder": {"specialist": "crypto", "market_type": "ladder",
                          "clv_bps_mean": 2000.0, "n_entries": 50,
                          "clv_bps_ci95_lower": 100, "clv_bps_ci95_upper": 3900},
        "mlb|winner": {"specialist": "mlb", "market_type": "winner",
                       "clv_bps_mean": 300.0, "n_entries": 10},
    }})
    _write(tmp_path / "mispricing_monitor_latest.json", {"shortlist": [
        {"ticker": "KXBTCD-A", "side": "YES", "edge": 0.2, "model_prob": 0.8,
         "book_prob": 0.7, "market_prob": 0.6, "confidence": "high", "ejection_events": []},
        {"ticker": "KXMLBTOTAL-x", "side": "NO", "edge": 0.1,
         "ejection_events": [{"player": "Star OF ejected"}]},
    ]})
    council = [
        {"name": "crypto", "status": "ok", "clv_bps": 2000, "contested_brier": 0.06, "in_season": True},
        {"name": "mlb", "status": "ok", "clv_bps": 300, "where_we_bleed": "mlb|total edge -0.02"},
    ]
    ex = build_scope_extras(tmp_path, [("CRYPTO", "BTC"), ("SPORTS", "MLB")], council_rows=council)

    btc, mlb = ex["CRYPTO"]["BTC"], ex["SPORTS"]["MLB"]
    assert btc["council"]["name"] == "crypto"                       # crypto specialist shared across coins
    assert any(c["market_type"] == "ladder" for c in btc["clv"])
    assert [m["ticker"] for m in btc["mispricing"]] == ["KXBTCD-A"]  # grouped by ticker scope
    assert mlb["council"]["name"] == "mlb"
    assert [m["ticker"] for m in mlb["mispricing"]] == ["KXMLBTOTAL-x"]
    assert len(mlb["ejections"]) == 1                                # ejection folded into its scope
    assert any(c["market_type"] == "winner" for c in mlb["clv"])


def test_scope_extras_missing_artifacts_safe(tmp_path):
    from autonomy.scope_analytics import build_scope_extras

    ex = build_scope_extras(tmp_path, [("CRYPTO", "BTC")], council_rows=None)
    assert ex["CRYPTO"]["BTC"] == {"council": None, "clv": [], "mispricing": [], "ejections": []}


def test_scopes_endpoint_merges_extras(tmp_path, monkeypatch):
    import json

    from starlette.testclient import TestClient

    import autonomy.dashboard as dash

    (tmp_path / "latest_dashboard_snapshot.json").write_text(json.dumps({
        "generated_at": "2026-07-19T18:00:00+00:00",
        "scopes": {"verticals": {"CRYPTO": {"scopes": {"BTC": {"summary": {"n": 3}}}}}},
        "backtest": {},
    }), encoding="utf-8")
    (tmp_path / "mispricing_monitor_latest.json").write_text(json.dumps({
        "shortlist": [{"ticker": "KXBTCD-Z", "side": "YES", "edge": 0.15}],
    }), encoding="utf-8")
    monkeypatch.setattr(dash, "RUNTIME_DIR", tmp_path)

    sc = TestClient(dash.build_app()).get("/api/scopes").json()
    extras = sc["verticals"]["CRYPTO"]["scopes"]["BTC"]["extras"]
    assert [m["ticker"] for m in extras["mispricing"]] == ["KXBTCD-Z"]
