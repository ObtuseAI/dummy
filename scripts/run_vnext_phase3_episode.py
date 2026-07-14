"""Replay and persist one fully frozen, shadow-only vNext Phase 3 episode."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dummy.organisms import (
    EpisodeRequest,
    HeldOutCase,
    IssuedEpisodeArtifact,
    IssueRequest,
    JsonlEpisodeLedger,
    VerifiedSettlement,
    complete_issued_episode,
    issue_episode,
    run_complete_episode,
    verify_deterministic_replay,
)


def _mapping(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("episode input must be a JSON object")
    return payload


def _write_issued(path: Path, artifact: IssuedEpisodeArtifact) -> None:
    if path.exists():
        existing = IssuedEpisodeArtifact(_mapping(path))
        if existing.to_json() != artifact.to_json():
            raise ValueError("issued artifact path already contains different bytes")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(artifact.to_json())
        handle.write("\n")


def _summary(**values: Any) -> None:
    print(json.dumps(values, sort_keys=True, separators=(",", ":")))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Issue, later complete, or deterministically replay a shadow-only "
            "vNext Phase 3 episode."
        )
    )
    commands = parser.add_subparsers(dest="command", required=True)
    issue = commands.add_parser(
        "issue",
        help="Freeze steps 1-13 from decision-time evidence only.",
    )
    issue.add_argument("--input", type=Path, required=True)
    issue.add_argument("--output", type=Path, required=True)

    complete = commands.add_parser(
        "complete",
        help="Attach later verified truth without rerunning the organism.",
    )
    complete.add_argument("--issued", type=Path, required=True)
    complete.add_argument(
        "--truth",
        type=Path,
        required=True,
        help="JSON object with settlement and held_out_cases.",
    )
    complete.add_argument("--ledger", type=Path, required=True)

    replay = commands.add_parser(
        "replay",
        help="Verify a complete frozen request twice, then append it.",
    )
    replay.add_argument("--input", type=Path, required=True)
    replay.add_argument("--ledger", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "issue":
        issued = issue_episode(IssueRequest.from_dict(_mapping(args.input)))
        _write_issued(args.output, issued)
        _summary(
            episode_id=issued.episode_id,
            issuance_digest=issued.digest(),
            status="ISSUED",
            execution_authority=False,
            output=str(args.output.resolve()),
        )
        return 0

    if args.command == "complete":
        issued = IssuedEpisodeArtifact(_mapping(args.issued))
        truth = _mapping(args.truth)
        artifact = complete_issued_episode(
            issued,
            settlement=VerifiedSettlement.from_dict(truth["settlement"]),
            held_out_cases=tuple(
                HeldOutCase.from_dict(item) for item in truth["held_out_cases"]
            ),
            ledger=JsonlEpisodeLedger(args.ledger),
        )
        _summary(
            episode_id=artifact.episode_id,
            artifact_digest=artifact.digest(),
            issuance_digest=issued.digest(),
            status="DISSOLVED",
            execution_authority=False,
            promotion_authority="HUMAN_ONLY",
            ledger=str(args.ledger.resolve()),
        )
        return 0

    request = EpisodeRequest.from_dict(_mapping(args.input))
    verification = verify_deterministic_replay(request)
    artifact = run_complete_episode(
        request,
        ledger=JsonlEpisodeLedger(args.ledger),
    )
    _summary(
        episode_id=artifact.episode_id,
        artifact_digest=artifact.digest(),
        byte_identical_replay=verification.byte_identical,
        status=artifact.to_dict()["status"],
        execution_authority=False,
        promotion_authority="HUMAN_ONLY",
        ledger=str(args.ledger.resolve()),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
