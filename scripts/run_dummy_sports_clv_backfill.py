#!/usr/bin/env python
"""Best-effort sports CLV backfill (Wave-2 workstream D1).

Reconstructs APPROXIMATE pre-game closing lines for sports markets from a
historical book-tape snapshot, so months of already-captured book prices can
seed the CLV report instead of waiting for fresh live capture. Read-only
against its inputs; it never writes into the live runtime.

Why a backfill is needed: before Wave-2 D1 the monitor taped sports markets
with ``close_time`` = the Kalshi contract close (game END), so no pre-game
close was ever selected (autonomy/clv.py's ``select_close`` anchors on
``close_time``) and ``clv_report.json`` carried zero sports scopes. The raw
snapshots ARE on the historical tape, though -- each pass recorded the
de-vigged book price + Kalshi mid. This tool re-anchors them: for every sports
ticker it resolves the game's scheduled start (ESPN scoreboard, the same
``Game.date`` the live tracker uses), takes the LAST pre-game snapshot within
the CLV close window as the approximate close, and re-emits it with
``close_time`` = first pitch and ``backfilled: true``.

Honesty: every reconstructed row is flagged ``backfilled: true`` so the grader
(autonomy/clv.py propagates the flag into graded rows and a per-scope
``n_backfilled_entries`` count) and any reviewer can see which CLV evidence is
approximated rather than live-captured. Fail-closed everywhere: a ticker whose
game start cannot be resolved, or that has no pre-game snapshot inside the
window, contributes NOTHING rather than a guessed close.

Operator usage (run against a COPY / an explicit --tape path, never the live
runtime; ESPN network is used to resolve historical starts):

    python scripts/run_dummy_sports_clv_backfill.py \
        --tape D:/DummyRuntime/autonomy/book_tape.jsonl \
        --out  runtime/autonomy/book_tape_sports_backfill.jsonl

then grade the reconstructed tape (its non-sports rows pass through unchanged,
so crypto CLV is preserved):

    python scripts/run_dummy_clv_grader.py \
        --tape    runtime/autonomy/book_tape_sports_backfill.jsonl \
        --entries D:/DummyRuntime/autonomy/paper_entries.jsonl \
        --out     runtime/autonomy/clv_report_backfill.json

This tool has no session, execution, or capital authority and changes no live
parameter.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.clv import CLOSE_WINDOW_MINUTES, _parse_ts  # noqa: E402
from autonomy.ontology import MarketView, Vertical  # noqa: E402

IN_PATH = Path("runtime/autonomy/book_tape.jsonl")
OUT_PATH = Path("runtime/autonomy/book_tape_sports_backfill.jsonl")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def reconstruct_closes(
    tape_rows: list[dict[str, Any]],
    start_resolver: Callable[[str], str | None],
    *,
    window_minutes: float = CLOSE_WINDOW_MINUTES,
) -> list[dict[str, Any]]:
    """One approximate pre-game close per resolvable sports ticker.

    Pure and deterministic given ``start_resolver`` (injected for tests). For
    each ticker: resolve its scheduled start, then pick the LAST tape snapshot
    that is strictly pre-game (``ts < start``), carries a real ``book_prob``,
    and lands within ``window_minutes`` of first pitch -- exactly the row the
    live ``select_close`` would have chosen had the tape been anchored on game
    start. Fail-closed: no start, or no qualifying snapshot -> no row.
    """
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for row in tape_rows:
        ticker = row.get("ticker")
        if ticker:
            by_ticker.setdefault(str(ticker), []).append(row)

    out: list[dict[str, Any]] = []
    for ticker, rows in by_ticker.items():
        start_iso = start_resolver(ticker)
        if start_iso is None:
            continue
        start = _parse_ts(start_iso)
        if start is None:
            continue
        window_s = float(window_minutes) * 60.0
        best: dict[str, Any] | None = None
        best_ts: float | None = None
        for row in rows:
            ts = _parse_ts(row.get("ts"))
            if ts is None or row.get("book_prob") is None:
                continue
            if ts >= start or (start - ts) > window_s:
                continue  # pre-game only, inside the close window
            if best_ts is None or ts > best_ts:  # last snapshot before first pitch
                best, best_ts = row, ts
        if best is None:
            continue
        out.append({
            "ticker": ticker,
            "ts": best.get("ts"),
            "book_prob": best.get("book_prob"),
            "kalshi_mid": best.get("kalshi_mid"),
            "close_time": start_iso,
            "backfilled": True,
        })
    return out


def build_backfilled_tape(
    tape_rows: list[dict[str, Any]],
    start_resolver: Callable[[str], str | None],
    *,
    window_minutes: float = CLOSE_WINDOW_MINUTES,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(grader-ready tape, reconstructed rows).

    The grader-ready tape is every row for tickers we did NOT reconstruct
    (crypto, and sports we could not resolve -- passed through untouched so
    existing crypto CLV is preserved) PLUS the single reconstructed close per
    reconstructed sports ticker. The reconstructed ticker's original rows are
    dropped so their game-END-anchored prices cannot contaminate select_close.
    """
    reconstructed = reconstruct_closes(
        tape_rows, start_resolver, window_minutes=window_minutes,
    )
    recon_tickers = {row["ticker"] for row in reconstructed}
    passthrough = [
        row for row in tape_rows if str(row.get("ticker")) not in recon_tickers
    ]
    return passthrough + reconstructed, reconstructed


class EspnStartResolver:
    """ticker -> scheduled game-start ISO via the ESPN scoreboard (live network).

    Resolves the league/date/competitors from the ticker through the same
    ``parse_sports_contract`` the specialists use, then locates the game.
    Winner markets parse from the ticker alone (teams + date are encoded);
    total/spread tickers need the market title/strike the tape does not carry,
    so they simply do not resolve here -- the moneyline (#2 measured edge) is
    the target. Fail-closed to None on any parse/lookup failure.
    """

    def __init__(self, espn_factory: Callable[[], Any] | None = None) -> None:
        from autonomy.sports.espn import EspnClient

        self._factory = espn_factory or (lambda: EspnClient())
        self._clients: dict[str, Any] = {}

    def _client(self, league: str) -> Any:
        return self._clients.setdefault(league, self._factory())

    def __call__(self, ticker: str) -> str | None:
        from autonomy.signals.sports_intelligence import parse_sports_contract

        try:
            market = MarketView(
                ticker=ticker, title="", vertical=Vertical.SPORTS, status="",
                close_time="", yes_bid=None, yes_ask=None, no_bid=None, no_ask=None,
                volume=0, liquidity=0, raw={},
            )
            parsed = parse_sports_contract(market)
            if parsed is None or not parsed.competitors:
                return None
            client = self._client(parsed.sport)
            if parsed.market_type == "winner":
                game = client.find_matchup(
                    parsed.sport, parsed.competitors[0], parsed.competitors[1],
                    parsed.date_yyyymmdd,
                )
            else:
                game = client.find_matchup_names(
                    parsed.sport, parsed.competitors[0], parsed.competitors[1],
                    parsed.date_yyyymmdd,
                )
            return game.date if game is not None and game.date else None
        except Exception:
            return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tape", type=Path, default=IN_PATH,
                        help="historical book_tape.jsonl to reconstruct from (read-only)")
    parser.add_argument("--out", type=Path, default=OUT_PATH,
                        help="grader-ready tape to write (non-sports rows passed "
                             "through; reconstructed sports closes flagged backfilled)")
    parser.add_argument("--window-minutes", type=float, default=CLOSE_WINDOW_MINUTES,
                        help="pre-game snapshot must be within this many minutes of "
                             "first pitch to stand in as the close")
    args = parser.parse_args()

    tape_rows = _load_jsonl(args.tape)
    resolver = EspnStartResolver()
    grader_tape, reconstructed = build_backfilled_tape(
        tape_rows, resolver, window_minutes=args.window_minutes,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for row in grader_tape:
            handle.write(json.dumps(row, sort_keys=True))
            handle.write("\n")

    print(json.dumps({
        "status": "OK",
        "tape_rows_in": len(tape_rows),
        "reconstructed_closes": len(reconstructed),
        "reconstructed_tickers": sorted({r["ticker"] for r in reconstructed})[:20],
        "grader_tape_rows_out": len(grader_tape),
        "out": str(args.out),
        "note": "reconstructed closes flagged backfilled=true; approximate "
                "pre-game closes re-anchored on ESPN scheduled game start.",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
