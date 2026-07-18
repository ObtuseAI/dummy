"""Wave-15: the bet board (every priced market, ranked, league x bet type)."""
from __future__ import annotations

from autonomy.bet_board import assemble_bet_board
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Signal
from autonomy.picks import FUSED_SOURCE


def _emit(ledger, ticker, p, market_p=None, when=None, source=FUSED_SOURCE):
    from datetime import datetime, timedelta, timezone

    created = when or (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    features = {"challenger_only": False, "is_fused_output": True}
    if market_p is not None:
        features["market_implied_yes"] = market_p
    ledger.record_signal(Signal(
        source=source, market_ticker=ticker, probability_yes=p,
        uncertainty=0.1, rationale="r", created_at=created, features=features))


def test_board_groups_ranks_and_computes_edge(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    _emit(ledger, "KXMLBGAME-26JUL18NYYBOS-NYY", 0.71, market_p=0.55)   # +16 edge
    _emit(ledger, "KXWNBATOTAL-26JUL18LVANYL-T164", 0.58, market_p=0.55)  # +3
    _emit(ledger, "KXWNBA1HTOTAL-26JUL18LVANYL-T80", 0.44, market_p=0.50)  # -6
    board = assemble_bet_board(conn=ledger._conn)
    assert board["rows"] == 3
    assert board["top"][0]["ticker"] == "KXMLBGAME-26JUL18NYYBOS-NYY"
    assert board["top"][0]["rank"] == 1
    assert abs(board["top"][0]["edge"] - 0.16) < 1e-9
    assert board["top"][0]["pick"] == "yes" and board["top"][0]["tier"] == "A"
    assert "mlb" in board["groups"] and "winner" in board["groups"]["mlb"]
    # Segment bet types carry their segment label.
    assert "h1_total" in board["groups"]["wnba"]
    assert board["groups"]["wnba"]["h1_total"][0]["pick"] == "no"


def test_board_uses_latest_emission_and_drops_settled(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    ticker = "KXMLBGAME-26JUL18NYYBOS-NYY"
    from datetime import datetime, timedelta, timezone

    early = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    late = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    _emit(ledger, ticker, 0.40, market_p=0.5, when=early)
    _emit(ledger, ticker, 0.66, market_p=0.5, when=late)
    settled = "KXMLBGAME-26JUL18AAABBB-AAA"
    _emit(ledger, settled, 0.80, market_p=0.5)
    ledger.record_settlement(settled, True)
    board = assemble_bet_board(conn=ledger._conn)
    assert board["rows"] == 1
    assert board["top"][0]["probability"] == 0.66


def test_board_no_pick_band_and_missing_market_prob(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    _emit(ledger, "KXMLBGAME-26JUL18CCCDDD-CCC", 0.505)      # coin flip, no market
    board = assemble_bet_board(conn=ledger._conn)
    row = board["top"][0]
    assert row["pick"] is None and row["tier"] is None
    assert row["edge"] is None and row["market_probability"] is None


def test_board_missing_db_is_an_error_payload_not_a_crash(tmp_path):
    board = assemble_bet_board(
        db_path=str(tmp_path / "absent" / "ledger.db"),
        artifact_path=tmp_path / "absent" / "bet_board.json")
    assert board["rows"] == 0
    assert "groups" in board


class _Mkt:
    def __init__(self, ticker, title):
        self.ticker, self.title = ticker, title


class _Fc:
    def __init__(self, p, market_p, unc=0.1):
        self.probability_yes = p
        self.market_implied_yes = market_p
        self.uncertainty = unc


def test_cycle_artifact_writes_and_serves_first(tmp_path):
    from autonomy.bet_board import write_board_artifact

    path = tmp_path / "bet_board.json"
    written = write_board_artifact(
        [
            (_Mkt("KXMLBGAME-26JUL18NYYBOS-NYY", "Yankees vs Red Sox Winner?"),
             _Fc(0.71, 0.55)),
            (_Mkt("KXWNBA1HTOTAL-26JUL18LVANYL-T80", "Aces vs Liberty 1H Total?"),
             _Fc(0.44, 0.50)),
        ],
        path=path,
    )
    assert written["rows"] == 2
    assert written["top"][0]["title"] == "Yankees vs Red Sox Winner?"
    assert written["top"][0]["edge"] == 0.16
    assert written["source"] == "cycle_artifact"

    served = assemble_bet_board(
        db_path=str(tmp_path / "no.db"), artifact_path=path)
    assert served["rows"] == 2 and served["source"] == "cycle_artifact"
    assert served["age_seconds"] >= 0
    assert "h1_total" in served["groups"]["wnba"]


def test_stale_artifact_falls_back_to_ledger(tmp_path):
    from autonomy.bet_board import write_board_artifact

    path = tmp_path / "bet_board.json"
    write_board_artifact(
        [(_Mkt("KXMLBGAME-26JUL18NYYBOS-NYY", "t"), _Fc(0.7, 0.5))],
        path=path, now_iso="2026-07-01T00:00:00+00:00")   # ancient
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    _emit(ledger, "KXMLBGAME-26JUL18CCCDDD-CCC", 0.61, market_p=0.5)
    board = assemble_bet_board(
        db_path=str(tmp_path / "ledger.db"), artifact_path=path)
    assert board["source"] == "ledger_fallback"
    assert board["rows"] == 1
