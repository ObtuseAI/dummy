"""Run Dummy's bounded real-ledger autoresearch and forward-paper cycle."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dummy.autoresearch.campaign import (  # noqa: E402
    run_loop1_campaign,
    write_campaign_report,
)
from dummy.autoresearch.forward_paper import (  # noqa: E402
    build_forward_registry,
    grade_forward_observations,
    issue_forward_observations,
    write_forward_artifact,
)
from dummy.autoresearch.ledger_pipeline import (  # noqa: E402
    build_ledger_partition_plan,
    load_ledger_evidence,
)
from dummy.autoresearch.operational_ignition import (  # noqa: E402
    operational_ignition_report,
    record_campaign_ignition_trial,
    write_ignition_report,
)
from dummy.genome import pilot_genomes  # noqa: E402


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
    rows = load_ledger_evidence(ledger_path, ticker_prefix=ticker_prefix)
    scope = "crypto|btc|15m_direction|15m"
    plan = build_ledger_partition_plan(rows, scope=scope)
    base = next(
        genome
        for genome in pilot_genomes()
        if genome.vertical.lower() == "crypto"
        and genome.market_type == "15m_direction"
    )
    evidence_cutoff = max(row.settlement_received_at for row in rows)
    campaign_created_at = evidence_cutoff + timedelta(microseconds=1)
    campaign = run_loop1_campaign(
        rows=rows,
        plan=plan,
        base_genome=base,
        created_at=campaign_created_at,
    )
    campaign_path = output_dir / "campaign_report.json"
    registry_path = output_dir / "forward_registry.json"
    observation_path = output_dir / "forward_observations.jsonl"
    forward_path = output_dir / "forward_report.json"
    trial_path = output_dir / "ignition_trials.jsonl"
    ignition_path = output_dir / "ignition_report.json"
    write_campaign_report(campaign, campaign_path)
    registry = build_forward_registry(
        campaign,
        base_genome=base,
        ticker_prefix=ticker_prefix,
        existing=_read_json(registry_path),
    )
    write_forward_artifact(registry, registry_path)
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
    write_forward_artifact(forward, forward_path)
    trial = record_campaign_ignition_trial(
        campaign,
        trial_ledger_path=trial_path,
    )
    ignition = operational_ignition_report(
        trial_ledger_path=trial_path,
        forward_report=forward,
    )
    write_ignition_report(ignition, ignition_path)
    return {
        "campaign_id": campaign["campaign_id"],
        "scope": scope,
        "evidence_rows": len(rows),
        "private_trials": campaign["genuine_private_candidate_trials"],
        "private_survivors": campaign["private_survivors"],
        "external_survivors": campaign["external_survivors"],
        "forward_observations_issued": issuance["new_observations"],
        "forward_settlements": forward["forward_paper_candidate_settlements"],
        "ignition_trial_id": trial.trial_id,
        "highest_supported_level": ignition[
            "highest_supported_recursive_improvement_level"
        ],
        "orders_placed": False,
        "execution_authority": False,
        "outputs": {
            "campaign": str(campaign_path),
            "forward_registry": str(registry_path),
            "forward_report": str(forward_path),
            "ignition_report": str(ignition_path),
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
