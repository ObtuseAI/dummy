"""Emit deterministic Phase 7 homeostasis, arena, and observatory evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dummy.arenas import (  # noqa: E402
    arena_catalog_manifest,
    arena_reproducibility_report,
)
from dummy.constitution import protected_manifest_dict  # noqa: E402
from dummy.evolution import evaluate_evolution_family  # noqa: E402
from dummy.genome import genome_catalog_manifest  # noqa: E402
from dummy.homeostasis import DEFAULT_HEALTH_POLICIES, HealthVariable  # noqa: E402
from dummy.observatory import build_phase7_observatory_snapshot  # noqa: E402
from dummy.world_model.models import digest_json  # noqa: E402
from scripts.run_vnext_phase6_audit import evolution_policy_manifest  # noqa: E402


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def homeostasis_policy_manifest() -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": 1,
        "phase": 7,
        "variable_count": len(HealthVariable),
        "variables": [item.value for item in HealthVariable],
        "policies": [item.to_dict() for item in DEFAULT_HEALTH_POLICIES],
        "runtime_reading_count": 0,
        "runtime_status": "NO_LIVE_VNEXT_TELEMETRY",
        "unknown_reading_behavior": "FAIL_CLOSED_REQUEST_EVIDENCE",
        "interventions_applied": False,
        "authority_expansion_allowed": False,
        "execution_authority": False,
        "performance_claim_supported": False,
    }
    body["manifest_id"] = digest_json(body)
    return body


def build_outputs() -> dict[str, dict[str, Any]]:
    homeostasis = homeostasis_policy_manifest()
    catalog = arena_catalog_manifest()
    arena_report = arena_reproducibility_report()
    genomes = genome_catalog_manifest()
    evolution = evaluate_evolution_family(())
    observatory = build_phase7_observatory_snapshot(
        homeostasis_manifest=homeostasis,
        arena_catalog_manifest=catalog,
        arena_report=arena_report,
        genome_catalog_manifest=genomes,
        evolution_evidence=evolution,
    ).to_dict()
    return {
        "VNEXT_PROTECTED_SURFACES.json": protected_manifest_dict(),
        "VNEXT_PHASE6_EVOLUTION_POLICY.json": evolution_policy_manifest(),
        "VNEXT_PHASE7_HOMEOSTASIS_POLICY.json": homeostasis,
        "VNEXT_PHASE7_ARENA_CATALOG.json": catalog,
        "VNEXT_PHASE7_ARENA_REPRODUCIBILITY.json": arena_report,
        "VNEXT_PHASE7_OBSERVATORY_SNAPSHOT.json": observatory,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs")
    args = parser.parse_args()
    outputs = build_outputs()
    for filename, payload in outputs.items():
        _write(args.output_dir / filename, payload)
    print(
        json.dumps(
            {
                "outputs": [str(args.output_dir / name) for name in outputs],
                "arena_scenario_count": outputs["VNEXT_PHASE7_ARENA_CATALOG.json"][
                    "scenario_count"
                ],
                "runtime_vnext_telemetry": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
