"""Append-only storage for dissolved vNext organism episodes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock
from typing import Iterable

from .models import EpisodeArtifact, EpisodeValidationError


class InMemoryEpisodeLedger:
    """Deterministic sink used for replay and isolated tests."""

    def __init__(self) -> None:
        self._records: dict[str, str] = {}

    def append(self, artifact: EpisodeArtifact) -> str:
        payload = artifact.to_json()
        existing = self._records.get(artifact.episode_id)
        if existing is not None and existing != payload:
            raise EpisodeValidationError(
                "episode ID collision has non-identical canonical bytes"
            )
        self._records[artifact.episode_id] = payload
        return artifact.episode_id

    def get(self, episode_id: str) -> EpisodeArtifact:
        try:
            raw = self._records[episode_id]
        except KeyError as exc:
            raise EpisodeValidationError(f"unknown episode_id: {episode_id}") from exc
        return EpisodeArtifact(json.loads(raw))

    def records(self) -> tuple[EpisodeArtifact, ...]:
        return tuple(self.get(key) for key in sorted(self._records))


class JsonlEpisodeLedger:
    """Fail-closed, append-only JSONL ledger outside the incumbent ledger."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = Lock()

    def _read_rows(self) -> Iterable[tuple[int, EpisodeArtifact, str]]:
        if not self.path.exists():
            return ()
        rows: list[tuple[int, EpisodeArtifact, str]] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                raw = line.rstrip("\n")
                if not raw.strip():
                    raise EpisodeValidationError(
                        f"blank organism ledger row at line {line_number}"
                    )
                try:
                    artifact = EpisodeArtifact(json.loads(raw))
                except (json.JSONDecodeError, TypeError, ValueError) as exc:
                    raise EpisodeValidationError(
                        f"invalid organism ledger row at line {line_number}"
                    ) from exc
                if raw != artifact.to_json():
                    raise EpisodeValidationError(
                        f"noncanonical organism ledger row at line {line_number}"
                    )
                rows.append((line_number, artifact, raw))
        return tuple(rows)

    def append(self, artifact: EpisodeArtifact) -> str:
        canonical = artifact.to_json()
        with self._lock:
            for _line_number, existing, raw in self._read_rows():
                if existing.episode_id != artifact.episode_id:
                    continue
                if raw != canonical:
                    raise EpisodeValidationError(
                        "episode ID collision has non-identical canonical bytes"
                    )
                return artifact.episode_id
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(canonical)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        return artifact.episode_id

    def get(self, episode_id: str) -> EpisodeArtifact:
        matches = tuple(
            artifact
            for _line_number, artifact, _raw in self._read_rows()
            if artifact.episode_id == episode_id
        )
        if len(matches) != 1:
            raise EpisodeValidationError(
                f"ledger requires exactly one record for episode_id: {episode_id}"
            )
        return matches[0]

    def records(self) -> tuple[EpisodeArtifact, ...]:
        rows = tuple(self._read_rows())
        ids = tuple(artifact.episode_id for _line, artifact, _raw in rows)
        if len(set(ids)) != len(ids):
            raise EpisodeValidationError("organism ledger contains duplicate episode IDs")
        return tuple(artifact for _line, artifact, _raw in rows)
