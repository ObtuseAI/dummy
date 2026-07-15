"""GET-only evidence projections for the DUMMY vNext observatory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"

router = APIRouter(prefix="/api/vnext", tags=["vnext-read-only-observatory"])


def _read(name: str) -> dict[str, Any]:
    path = DOCS / name
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"vNext artifact unavailable: {name}",
        ) from exc
    if not isinstance(value, dict):
        raise HTTPException(status_code=503, detail=f"vNext artifact malformed: {name}")
    return value


@router.get("/observatory")
def observatory() -> dict[str, Any]:
    return _read("VNEXT_PHASE7_OBSERVATORY_SNAPSHOT.json")


@router.get("/observatory/{panel_name}")
def observatory_panel(panel_name: str) -> dict[str, Any]:
    snapshot = observatory()
    for panel in snapshot.get("panels", []):
        if panel.get("panel") == panel_name:
            return panel
    raise HTTPException(status_code=404, detail="unknown vNext observatory panel")


@router.get("/arenas")
def arenas() -> dict[str, Any]:
    return _read("VNEXT_PHASE7_ARENA_REPRODUCIBILITY.json")


@router.get("/arena-catalog")
def arena_catalog() -> dict[str, Any]:
    return _read("VNEXT_PHASE7_ARENA_CATALOG.json")


@router.get("/homeostasis")
def homeostasis() -> dict[str, Any]:
    return _read("VNEXT_PHASE7_HOMEOSTASIS_POLICY.json")


__all__ = ["router"]
