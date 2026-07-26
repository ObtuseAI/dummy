#!/usr/bin/env python
"""Run one allowlisted registry-owned Dummy job with truthful supervision."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.job_supervisor import JobRegistryError, load_registry, run_job  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=Path("ops/job_registry.json"))
    parser.add_argument("--job", required=True)
    parser.add_argument(
        "--result-root",
        type=Path,
        default=Path("runtime/autonomy/jobs"),
    )
    args = parser.parse_args(argv)
    try:
        specs = load_registry(args.registry)
        if args.job not in specs:
            raise JobRegistryError(f"unknown job: {args.job}")
        result = run_job(
            specs[args.job],
            repo_root=Path(__file__).resolve().parent.parent,
            result_root=args.result_root,
        )
    except Exception as exc:
        print(json.dumps({
            "status": "REFUSED",
            "job": args.job,
            "error": f"{type(exc).__name__}:{exc}",
            "execution_authority": False,
        }, sort_keys=True))
        return 78
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return result.exit_code if 0 <= result.exit_code <= 255 else 1


if __name__ == "__main__":
    raise SystemExit(main())
