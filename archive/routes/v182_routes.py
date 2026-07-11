from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v182.reports import REPORT_GROUPS, V182ReportFactory

router = APIRouter(prefix="/api/v182", tags=["v182"])


def _safe(payload: dict[str, Any]) -> dict[str, Any]:
    payload["live_submit_disabled"] = True
    payload["caps_unchanged"] = True
    payload["execution_bridge_present"] = False
    payload["api_can_trigger_trading"] = False
    payload["api_can_submit_orders"] = False
    return payload


def _slice(*names: str) -> dict[str, Any]:
    reports = V182ReportFactory().build()
    return _safe({name.removesuffix(".json"): reports[name] for name in names})


def _route(group: str):
    async def handler() -> dict[str, Any]:
        return _slice(*REPORT_GROUPS[group])

    return handler


for _group in REPORT_GROUPS:
    router.add_api_route(f"/{_group}", _route(_group), methods=["GET"])
