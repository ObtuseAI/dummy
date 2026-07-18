"""Launch the autonomy evidence and paper-scheduler operator dashboard.

Usage:
    python scripts/run_dummy_dashboard.py [--port 8787]
Then open http://127.0.0.1:8787/ in a browser.

The only mutation surface starts or pauses the public-read-only paper scheduled
task. It has no route to broker submission, production weights, risk, or capital.
"""
from __future__ import annotations

import argparse
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    import uvicorn

    uvicorn.run(build_app(), host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
