"""Preregistration: hypothesis + falsification condition BEFORE results (Wave-7).

Ascendancy delta #2. The experiment ledger records what ran; it does not force
the researcher to commit to a mechanism and a kill condition before observing
the outcome. Preregistration closes that gap: a candidate rule enters a
campaign only after an immutable, content-addressed registration stating what
it claims, why it might work, and exactly what evidence falsifies it.

Rules:
  * A registration is append-only JSONL; entries are never edited.
  * The prereg_id is the digest of the semantic content — re-registering the
    identical claim is idempotent; changing any material field mints a NEW
    registration (the ledger keeps both, lineage is visible).
  * ``hypothesis``, ``mechanism`` and ``falsification_condition`` must be
    non-empty prose. "It works" is not a hypothesis; "loses money" is not a
    falsification condition (must reference measurable evidence).
  * Enforcement is opt-in per campaign (``require_preregistration=True``) so
    the change is prospective — existing pipelines are byte-identical until a
    campaign opts in.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dummy.world_model.models import digest_json

REGISTRY_PATH = Path("runtime/autonomy/preregistrations.jsonl")

_MIN_STATEMENT_CHARS = 20


class PreregistrationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Preregistration:
    prereg_id: str
    candidate_id: str
    lane: str
    hypothesis: str
    mechanism: str
    falsification_condition: str
    registered_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "prereg_id": self.prereg_id,
            "candidate_id": self.candidate_id,
            "lane": self.lane,
            "hypothesis": self.hypothesis,
            "mechanism": self.mechanism,
            "falsification_condition": self.falsification_condition,
            "registered_at": self.registered_at,
        }


def _semantic(candidate_id: str, lane: str, hypothesis: str,
              mechanism: str, falsification_condition: str) -> dict[str, str]:
    return {
        "schema_version": 1,
        "candidate_id": candidate_id,
        "lane": lane,
        "hypothesis": hypothesis,
        "mechanism": mechanism,
        "falsification_condition": falsification_condition,
    }


def _validate(name: str, value: str) -> str:
    text = str(value or "").strip()
    if len(text) < _MIN_STATEMENT_CHARS:
        raise PreregistrationError(
            f"{name} must be a substantive statement (>= {_MIN_STATEMENT_CHARS} chars); "
            f"got {text!r}"
        )
    return text


class PreregistrationRegistry:
    """Append-only registry of preregistered candidates."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or REGISTRY_PATH)

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        entries = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries

    def register(
        self,
        candidate_id: str,
        *,
        lane: str,
        hypothesis: str,
        mechanism: str,
        falsification_condition: str,
    ) -> Preregistration:
        candidate_id = str(candidate_id).strip()
        if not candidate_id:
            raise PreregistrationError("candidate_id is required")
        semantic = _semantic(
            candidate_id, str(lane).strip(),
            _validate("hypothesis", hypothesis),
            _validate("mechanism", mechanism),
            _validate("falsification_condition", falsification_condition),
        )
        prereg_id = digest_json(semantic)
        for entry in self._load():
            if entry.get("prereg_id") == prereg_id:
                return Preregistration(**{k: entry[k] for k in (
                    "prereg_id", "candidate_id", "lane", "hypothesis",
                    "mechanism", "falsification_condition", "registered_at")})
        record = Preregistration(
            prereg_id=prereg_id,
            candidate_id=candidate_id,
            lane=semantic["lane"],
            hypothesis=semantic["hypothesis"],
            mechanism=semantic["mechanism"],
            falsification_condition=semantic["falsification_condition"],
            registered_at=datetime.now(timezone.utc).isoformat(),
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")
        return record

    def is_registered(self, candidate_id: str) -> bool:
        return any(e.get("candidate_id") == candidate_id for e in self._load())

    def for_candidate(self, candidate_id: str) -> list[dict[str, Any]]:
        return [e for e in self._load() if e.get("candidate_id") == candidate_id]


def enforce_preregistered(
    candidate_ids: list[str], registry: PreregistrationRegistry,
) -> list[str]:
    """The unregistered subset (empty means every candidate may proceed)."""
    return [c for c in candidate_ids if not registry.is_registered(c)]
