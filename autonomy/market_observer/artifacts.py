"""Content-addressed, atomic persistence for market-observer evidence."""
from __future__ import annotations

import json
import math
import os
import re
import uuid
from pathlib import Path
from typing import Any

from autonomy.market_observer.contracts import (
    ObservationEnvelope,
    ObservationStatus,
    canonical_json,
    sha256_json,
)

_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9_.-]+$")


def _safe_component(value: Any) -> str:
    component = str(value)
    if not _SAFE_COMPONENT.fullmatch(component):
        raise ValueError(f"unsafe artifact path component: {component!r}")
    return component


def _atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class ContentAddressedArtifactStore:
    """Persist immutable blobs and atomic latest pointers.

    Only ``COMPLETE`` observations may advance the success pointer. A failure
    has its own pointer, so a partial refresh never hides the last valid data.
    """

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def write_raw(self, payload: Any) -> tuple[str, str]:
        raw_sha256 = sha256_json(payload)
        relative = Path("raw") / raw_sha256[:2] / f"{raw_sha256}.json"
        destination = self.root / relative
        serialized = canonical_json(payload)
        if destination.exists():
            if destination.read_text(encoding="utf-8").strip() != serialized:
                raise RuntimeError("content-addressed raw blob hash collision")
        else:
            _atomic_write(destination, serialized)
        return relative.as_posix(), raw_sha256

    def write_observation(self, envelope: ObservationEnvelope) -> Path:
        serialized = canonical_json(envelope.to_dict())
        observation_id = envelope.observation_id
        relative = Path("observations") / observation_id[:2] / f"{observation_id}.json"
        destination = self.root / relative
        if destination.exists():
            if destination.read_text(encoding="utf-8").strip() != serialized:
                raise RuntimeError("content-addressed observation hash collision")
        else:
            _atomic_write(destination, serialized)

        asset = _safe_component(envelope.requested.get("asset", "_"))
        timeframe = _safe_component(envelope.requested.get("timeframe", "_"))
        kind = _safe_component(envelope.kind)
        pointer_name = (
            "LATEST.json"
            if envelope.status is ObservationStatus.COMPLETE
            else "LATEST_FAILURE.json"
        )
        pointer = self.root / "by_request" / kind / asset / timeframe / pointer_name
        pointer_payload = canonical_json(
            {
                "schema_version": 1,
                "observation_id": observation_id,
                "status": envelope.status.value,
                "artifact_ref": relative.as_posix(),
                "received_at_s": envelope.received_at_s,
            }
        )
        _atomic_write(pointer, pointer_payload)
        return destination

    def read_latest(
        self,
        kind: str,
        asset: str,
        timeframe: str,
        *,
        include_failure: bool = False,
    ) -> dict[str, Any] | None:
        pointer_name = "LATEST_FAILURE.json" if include_failure else "LATEST.json"
        pointer = (
            self.root
            / "by_request"
            / _safe_component(kind)
            / _safe_component(asset)
            / _safe_component(timeframe)
            / pointer_name
        )
        if not pointer.exists():
            return None
        pointer_value = json.loads(pointer.read_text(encoding="utf-8"))
        if not isinstance(pointer_value, dict) or pointer_value.get("schema_version") != 1:
            raise ValueError("invalid artifact pointer schema")
        observation_id = str(pointer_value["observation_id"])
        if not re.fullmatch(r"[0-9a-f]{64}", observation_id):
            raise ValueError("invalid observation identity")
        pointer_status = str(pointer_value.get("status") or "")
        if (
            (not include_failure and pointer_status != ObservationStatus.COMPLETE.value)
            or (include_failure and pointer_status == ObservationStatus.COMPLETE.value)
            or pointer_status not in {status.value for status in ObservationStatus}
        ):
            raise ValueError("artifact pointer status violates pointer disposition")
        pointer_received_at = pointer_value.get("received_at_s")
        if (
            isinstance(pointer_received_at, bool)
            or not isinstance(pointer_received_at, (int, float))
            or not math.isfinite(float(pointer_received_at))
        ):
            raise ValueError("invalid artifact pointer receipt timestamp")
        artifact_ref = Path(str(pointer_value["artifact_ref"]))
        if artifact_ref.is_absolute() or ".." in artifact_ref.parts:
            raise ValueError("invalid artifact pointer")
        expected_ref = (
            Path("observations")
            / observation_id[:2]
            / f"{observation_id}.json"
        )
        if artifact_ref != expected_ref:
            raise ValueError("artifact pointer is not content-addressed")
        artifact = self.root / artifact_ref
        value = json.loads(artifact.read_text(encoding="utf-8"))
        if value.get("observation_id") != observation_id:
            raise ValueError("artifact pointer identity mismatch")
        identity = dict(value)
        identity.pop("observation_id", None)
        if sha256_json(identity) != observation_id:
            raise ValueError("observation content hash mismatch")
        if (
            value.get("status") != pointer_status
            or value.get("received_at_s") != pointer_received_at
        ):
            raise ValueError("artifact pointer metadata mismatch")
        requested = value.get("requested")
        if (
            value.get("kind") != str(kind)
            or not isinstance(requested, dict)
            or requested.get("asset") != str(asset)
            or requested.get("timeframe") != str(timeframe)
        ):
            raise ValueError("artifact pointer request identity mismatch")
        return value
