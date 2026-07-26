"""Launch Dummy's canonical, loopback-only evidence dashboard.

Usage:
    python scripts/run_dummy_dashboard.py [--port 8787]
Then open http://127.0.0.1:8787/ in a browser.

The application exposes GET/HEAD/OPTIONS only. It has no broker, authority,
configuration, scheduler, risk, or capital mutation surface.
"""
from __future__ import annotations

import argparse
import ipaddress
import os
import sys
from pathlib import Path

# Windowless launch (pythonw, the scheduled task): stdio handles are None and
# uvicorn's default logging dies wiring a StreamHandler to them. Point both at
# a log file so the server survives headless and stays debuggable.
if sys.stdout is None or sys.stderr is None:
    _log_dir = Path(__file__).resolve().parent.parent / "runtime" / "autonomy"
    _log_dir.mkdir(parents=True, exist_ok=True)
    _stream = open(_log_dir / "dashboard_stdout.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stdout or _stream
    sys.stderr = sys.stderr or _stream

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.dashboard import build_app  # noqa: E402


def validate_loopback_host(value: str) -> str:
    """Accept only literal loopback addresses or the exact localhost name."""
    candidate = str(value or "").strip().casefold().rstrip(".")
    if candidate == "localhost":
        return candidate
    try:
        address = ipaddress.ip_address(candidate.split("%", 1)[0])
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "dashboard host must be localhost or a literal loopback address"
        ) from exc
    if not address.is_loopback:
        raise argparse.ArgumentTypeError(
            "dashboard host must be loopback; remote and tailnet binds are disabled"
        )
    return str(address)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=int(os.environ.get("DUMMY_DASHBOARD_PORT", "8787")))
    parser.add_argument(
        "--host",
        type=validate_loopback_host,
        default=validate_loopback_host(
            os.environ.get("DUMMY_DASHBOARD_HOST", "127.0.0.1")
        ),
        help="loopback address only (default: 127.0.0.1)",
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    import uvicorn

    uvicorn.run(build_app(), host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
