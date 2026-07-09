"""Autonomous predator session control. The only operator surface.

Usage:
    python scripts/run_dummy_autonomous.py start [--live --ack "<exact phrase>"] [--hours H] [--interval S]
    python scripts/run_dummy_autonomous.py once [--live]
    python scripts/run_dummy_autonomous.py status
    python scripts/run_dummy_autonomous.py stop

Shadow mode (default) runs the full pipeline against live public market data
but records orders only in the shadow book — the calibration bootstrap.
LIVE mode requires the exact typed acknowledgement and routes every order
through the hardened Kalshi LiveBrokerFirewall adapter, LIMIT only, sized by
the self-managed risk brain. `stop` writes the kill file and disarms.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.executor import AUTONOMY_ACK, load_session
from autonomy.ontology import SessionMode
from autonomy.session import build_brain, session_status, start_session, stop_session


def _print(data) -> None:
    print(json.dumps(data, indent=2, sort_keys=True, default=str))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("start", "stop", "status", "once", "canary"))
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--ack", default="")
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--interval", type=float, default=120.0)
    parser.add_argument("--operator", default="chris")
    parser.add_argument("--override-evidence-gate", action="store_true",
                        help="Deliberately bypass the live evidence gate (operator intent only)")
    args = parser.parse_args()

    if args.command == "status":
        _print(session_status())
        return 0

    if args.command == "canary":
        from autonomy.session import canary_readiness

        _print(canary_readiness(check_balance=args.live))
        return 0

    if args.command == "stop":
        _print(stop_session())
        return 0

    mode = SessionMode.LIVE if args.live else SessionMode.SHADOW

    if args.command == "once":
        # One cycle without a persistent session (shadow) or with the current
        # session authority (live re-validated inside the executor).
        brain = build_brain(mode)
        report = asyncio.run(brain.run_cycle())
        _print(report.to_dict())
        return 0

    result = start_session(mode, ack=args.ack, hours=args.hours, operator=args.operator,
                           override_evidence_gate=args.override_evidence_gate)
    _print(result)
    if not result.get("started"):
        return 2

    brain = build_brain(mode)

    def should_continue() -> bool:
        session = load_session()
        return bool(session.get("valid")) and session.get("mode") == mode.value

    from autonomy.brain import run_loop

    try:
        reports = asyncio.run(run_loop(brain, args.interval, should_continue))
    except KeyboardInterrupt:
        _print(stop_session())
        return 0
    _print({"cycles": len(reports), "last": reports[-1].to_dict() if reports else None})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
