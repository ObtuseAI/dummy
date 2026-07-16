"""Run Dummy's bounded real-ledger autoresearch and forward-paper cycle."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dummy.autoresearch.campaign import write_campaign_report  # noqa: E402
from dummy.autoresearch.forward_paper import (  # noqa: E402
    build_forward_registry,
    grade_forward_observations,
    issue_forward_observations,
    write_forward_artifact,
)
from dummy.autoresearch.ledger_pipeline import load_ledger_evidence  # noqa: E402
from dummy.autoresearch.multi_cohort import (  # noqa: E402
    run_multi_cohort_campaigns,
)
from dummy.autoresearch.operational_ignition import (  # noqa: E402
    operational_ignition_report,
    record_campaign_ignition_trial,
    write_ignition_report,
)
from dummy.genome import ForecastGenome  # noqa: E402
from dummy.intelligence_lab import run_intelligence_research_cycle  # noqa: E402


def _read_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return value if isinstance(value, dict) else None


def _parse_time(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("--issued-at must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def run_cycle(
    *,
    ledger_path: Path,
    output_dir: Path,
    ticker_prefix: str,
    issued_at: datetime,
) -> dict[str, object]:
    rows = load_ledger_evidence(ledger_path)
    multi = run_multi_cohort_campaigns(
        rows=rows,
        output_dir=output_dir,
    )
    campaign_path = output_dir / "campaign_report.json"
    registry_path = output_dir / "forward_registry.json"
    forward_path = output_dir / "forward_report.json"
    trial_path = output_dir / "ignition_trials.jsonl"
    ignition_path = output_dir / "ignition_report.json"
    forward_cohorts: list[dict[str, object]] = []
    trials = []
    primary: dict[str, object] | None = None
    normalized_prefix = ticker_prefix.upper()
    for entry in multi["campaigns"]:
        campaign = entry["campaign"]
        base = ForecastGenome.from_dict(entry["base_genome"])
        cohort_dir = Path(entry["cohort_output_dir"])
        cohort_registry_path = cohort_dir / "forward_registry.json"
        observation_path = cohort_dir / "forward_observations.jsonl"
        cohort_forward_path = cohort_dir / "forward_report.json"
        registry = build_forward_registry(
            campaign,
            base_genome=base,
            ticker_prefix=str(entry["ticker_prefix"]),
            existing=_read_json(cohort_registry_path),
        )
        write_forward_artifact(registry, cohort_registry_path)
        issuance = issue_forward_observations(
            registry,
            ledger_path=ledger_path,
            observation_ledger_path=observation_path,
            issued_at=issued_at,
        )
        forward = grade_forward_observations(
            registry,
            ledger_path=ledger_path,
            observation_ledger_path=observation_path,
        )
        forward["latest_issuance"] = issuance
        write_forward_artifact(forward, cohort_forward_path)
        trial = record_campaign_ignition_trial(
            campaign,
            trial_ledger_path=trial_path,
        )
        trials.append(trial)
        forward_cohorts.append(
            {
                "scope": entry["scope"],
                "registry_id": registry["registry_id"],
                "new_observations": issuance["new_observations"],
                "forward_settlements": forward["forward_paper_candidate_settlements"],
                "ready_for_human_promotion_review": forward[
                    "ready_for_human_promotion_review"
                ],
                "orders_placed": False,
                "execution_authority": False,
            }
        )
        if primary is None and (
            normalized_prefix.startswith(str(entry["ticker_prefix"]).upper())
            or str(entry["ticker_prefix"]).upper().startswith(normalized_prefix)
        ):
            if "15M" not in normalized_prefix or str(entry["scope"]).endswith("|15m"):
                primary = {
                    "campaign": campaign,
                    "registry": registry,
                    "forward": forward,
                    "issuance": issuance,
                    "trial": trial,
                    "scope": entry["scope"],
                }
    if primary is None and multi["campaigns"]:
        entry = multi["campaigns"][0]
        cohort_dir = Path(entry["cohort_output_dir"])
        primary = {
            "campaign": entry["campaign"],
            "registry": _read_json(cohort_dir / "forward_registry.json"),
            "forward": _read_json(cohort_dir / "forward_report.json"),
            "issuance": {},
            "trial": trials[0],
            "scope": entry["scope"],
        }
    if primary is None:
        raise ValueError("no exact cohort has enough evidence for autoresearch")

    write_campaign_report(primary["campaign"], campaign_path)
    write_forward_artifact(primary["registry"], registry_path)
    write_forward_artifact(primary["forward"], forward_path)
    aggregate_forward = {
        "schema_version": 1,
        "exact_cohorts": forward_cohorts,
        "forward_paper_candidate_settlements": sum(
            int(item["forward_settlements"]) for item in forward_cohorts
        ),
        "event_clusters": 0,
        "verified_settled_fills": 0,
        "ready_for_human_promotion_review": False,
        "orders_placed": False,
        "execution_authority": False,
    }
    write_forward_artifact(
        aggregate_forward,
        output_dir / "multi_forward_report.json",
    )
    ignition = operational_ignition_report(
        trial_ledger_path=trial_path,
        forward_report=aggregate_forward,
    )
    write_ignition_report(ignition, ignition_path)
    intelligence = run_intelligence_research_cycle(
        multi_cohort_report=multi,
        forward_report=aggregate_forward,
        ignition_report=ignition,
        output_dir=output_dir / "intelligence_lab",
        observed_at=issued_at,
    )
    campaign = primary["campaign"]
    issuance = primary["issuance"]
    forward = primary["forward"]
    trial = primary["trial"]
    return {
        "campaign_id": campaign["campaign_id"],
        "scope": primary["scope"],
        "evidence_rows": len(rows),
        "private_trials": campaign["genuine_private_candidate_trials"],
        "private_survivors": campaign["private_survivors"],
        "external_survivors": campaign["external_survivors"],
        "forward_observations_issued": int(issuance.get("new_observations", 0)),
        "forward_settlements": forward["forward_paper_candidate_settlements"],
        "ignition_trial_id": trial.trial_id,
        "highest_supported_level": ignition[
            "highest_supported_recursive_improvement_level"
        ],
        "intelligence_research": {
            "report_id": intelligence["report_id"],
            "opportunities": intelligence["cognitive_state"]["opportunities"],
            "proposed_experiments": intelligence["cognitive_state"][
                "proposed_experiments"
            ],
            "validated_theories": (
                intelligence["cognitive_state"]["provisional_theories"]
                + intelligence["cognitive_state"]["general_laws"]
            ),
            "highest_supported_level": intelligence["highest_supported_level"],
        },
        "orders_placed": False,
        "execution_authority": False,
        "multi_cohort": {
            "discovered": multi["discovered_cohorts"],
            "campaigns_completed": multi["campaigns_completed"],
            "forward_cohorts": len(forward_cohorts),
        },
        "outputs": {
            "campaign": str(campaign_path),
            "forward_registry": str(registry_path),
            "forward_report": str(forward_path),
            "ignition_report": str(ignition_path),
            "multi_cohort_report": str(output_dir / "multi_cohort_report.json"),
            "multi_forward_report": str(output_dir / "multi_forward_report.json"),
            "intelligence_observatory": str(
                output_dir / "intelligence_lab" / "observatory_report.json"
            ),
            "scientific_memory": str(
                output_dir / "intelligence_lab" / "scientific_memory.jsonl"
            ),
            "intelligence_research_queue": str(
                output_dir / "intelligence_lab" / "research_queue.json"
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ledger",
        type=Path,
        default=ROOT / "runtime" / "autonomy" / "ledger.db",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "runtime" / "autonomy" / "autoresearch",
    )
    parser.add_argument("--ticker-prefix", default="KXBTC15M")
    parser.add_argument("--issued-at")
    args = parser.parse_args()
    summary = run_cycle(
        ledger_path=args.ledger,
        output_dir=args.output_dir,
        ticker_prefix=args.ticker_prefix,
        issued_at=_parse_time(args.issued_at),
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
