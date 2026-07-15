"""Emit deterministic Phase 4 schema, ablation, and regime-transfer evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dummy.world_model import (  # noqa: E402
    WorldModelEvaluationCase,
    regime_transfer_report,
    supported_schema_manifest,
    world_state_ablation_report,
)


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _cases(path: Path | None) -> tuple[WorldModelEvaluationCase, ...]:
    if path is None:
        return ()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("evaluation input must be a JSON list")
    return tuple(WorldModelEvaluationCase.from_dict(item) for item in raw)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--minimum-cases", type=int, default=30)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs")
    args = parser.parse_args()
    cases = _cases(args.cases)
    outputs = {
        "VNEXT_PHASE4_WORLD_MODEL_SCHEMAS.json": supported_schema_manifest(),
        "VNEXT_PHASE4_WORLD_STATE_ABLATION.json": world_state_ablation_report(
            cases,
            minimum_cases=args.minimum_cases,
        ),
        "VNEXT_PHASE4_REGIME_TRANSFER.json": regime_transfer_report(
            cases,
            minimum_cases=args.minimum_cases,
        ),
    }
    for filename, payload in outputs.items():
        _write(args.output_dir / filename, payload)
    print(
        json.dumps(
            {
                "case_count": len(cases),
                "outputs": [str(args.output_dir / name) for name in outputs],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
