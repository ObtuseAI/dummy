"""Byte-level causal replay verification for complete organism episodes."""

from __future__ import annotations

from dataclasses import dataclass

from .episode import artifact_bytes, run_complete_episode
from .ledger import InMemoryEpisodeLedger
from .models import EpisodeRequest, EpisodeValidationError


@dataclass(frozen=True, slots=True)
class ReplayVerification:
    episode_id: str
    artifact_digest: str
    byte_identical: bool
    first_size_bytes: int
    second_size_bytes: int


def verify_deterministic_replay(request: EpisodeRequest) -> ReplayVerification:
    first = run_complete_episode(request, ledger=InMemoryEpisodeLedger())
    second = run_complete_episode(request, ledger=InMemoryEpisodeLedger())
    first_bytes = artifact_bytes(first)
    second_bytes = artifact_bytes(second)
    identical = first_bytes == second_bytes
    if not identical:
        raise EpisodeValidationError("causal replay produced non-identical bytes")
    return ReplayVerification(
        episode_id=first.episode_id,
        artifact_digest=first.digest(),
        byte_identical=True,
        first_size_bytes=len(first_bytes),
        second_size_bytes=len(second_bytes),
    )
