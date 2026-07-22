"""Run Dummy's manual-only exact four-model OpenRouter smoke."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model_router.openrouter_panel_smoke import (  # noqa: E402
    DEFAULT_ARTIFACT_PATH,
    run_openrouter_panel_smoke,
    write_redacted_smoke_report,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Preflight Dummy's exact OpenRouter panel. No network request is made "
            "unless --live is explicitly supplied."
        )
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Make one bounded request to each exact panel model.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=20.0,
        help="Per-call timeout in seconds (1-30; default: 20).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=512,
        help="Per-call output-token cap (64-512; default: 512).",
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        default=DEFAULT_ARTIFACT_PATH,
        help="Redacted evidence path used in --live mode.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = asyncio.run(
            run_openrouter_panel_smoke(
                live=args.live,
                timeout_seconds=args.timeout_seconds,
                max_tokens=args.max_tokens,
            )
        )
    except ValueError as exc:
        _parser().error(str(exc))

    if args.live:
        artifact = write_redacted_smoke_report(report, args.artifact.resolve())
        report = {**report, "artifact_path": str(artifact)}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] in {"PREFLIGHT_READY", "LIVE_PROVEN"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
