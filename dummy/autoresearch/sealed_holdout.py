"""Sealed one-shot holdout with a query-budget ledger (Wave-7).

Ascendancy delta #3. The partition plan already separates visible, private and
external evidence, but nothing STOPS a researcher from evaluating a candidate
against the external partition repeatedly until it passes — serial queries
leak the holdout back into development. This module makes the final
evaluation one-shot and ledgered:

  * Every submission is recorded in ``holdout_usage.jsonl`` (candidate,
    timestamp, result digest) BEFORE the result is returned.
  * A candidate's budget is one submission, ever. A failed sealed candidate
    stays failed; a repaired candidate is a NEW candidate id (new lineage),
    which is exactly the re-audit discipline the protocol demands.
  * The evaluator receives the sealed rows only inside the guarded call —
    there is no accessor that hands the raw rows back to the caller.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from dummy.world_model.models import digest_json

USAGE_PATH = Path("runtime/autonomy/holdout_usage.jsonl")
DEFAULT_BUDGET = 1


class HoldoutBudgetExceeded(RuntimeError):
    pass


class SealedHoldout:
    """Guards a sealed evidence partition behind a one-shot, ledgered gate."""

    def __init__(
        self,
        rows: Sequence[Any],
        *,
        usage_path: Path | None = None,
        budget_per_candidate: int = DEFAULT_BUDGET,
    ) -> None:
        self._rows = tuple(rows)
        self.usage_path = Path(usage_path or USAGE_PATH)
        self.budget = max(1, int(budget_per_candidate))

    # No public accessor exposes self._rows: evaluation happens only through
    # submit(), and the usage row is written before the result escapes.

    def _usage(self) -> list[dict[str, Any]]:
        if not self.usage_path.exists():
            return []
        out = []
        for line in self.usage_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    def submissions_for(self, candidate_id: str) -> int:
        return sum(
            1 for e in self._usage()
            if e.get("candidate_id") == candidate_id and e.get("kind") != "completion"
        )

    def submit(
        self,
        candidate_id: str,
        evaluate: Callable[[tuple[Any, ...]], dict[str, Any]],
    ) -> dict[str, Any]:
        """One-shot sealed evaluation for ``candidate_id``.

        Raises :class:`HoldoutBudgetExceeded` on any repeat submission. The
        usage entry is appended BEFORE evaluation so a crashed or killed
        evaluation still consumes the budget (fail-closed: you cannot peek by
        crashing).
        """
        candidate_id = str(candidate_id).strip()
        if not candidate_id:
            raise ValueError("candidate_id is required")
        used = self.submissions_for(candidate_id)
        if used >= self.budget:
            raise HoldoutBudgetExceeded(
                f"candidate {candidate_id!r} has exhausted its sealed-holdout "
                f"budget ({used}/{self.budget}); a repaired candidate must be "
                "registered under a NEW candidate id"
            )
        self.usage_path.parent.mkdir(parents=True, exist_ok=True)
        pending = {
            "candidate_id": candidate_id,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "n_rows": len(self._rows),
            "result_digest": None,
        }
        with self.usage_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(pending, sort_keys=True) + "\n")
        result = evaluate(self._rows)
        if not isinstance(result, dict):
            result = {"result": result}
        stamped = {
            "candidate_id": candidate_id,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "result_digest": digest_json({"candidate_id": candidate_id,
                                          "result": json.loads(json.dumps(result, default=str))}),
            "kind": "completion",
        }
        with self.usage_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(stamped, sort_keys=True) + "\n")
        return result
