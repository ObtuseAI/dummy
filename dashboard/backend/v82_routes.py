from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v82.reports import REPORT_GROUPS, V82ReportFactory

router = APIRouter(prefix="/api/v82", tags=["v82"])


def _safe(payload: dict[str, Any]) -> dict[str, Any]:
    payload["live_submit_disabled"] = True
    payload["caps_unchanged"] = True
    payload["execution_bridge_present"] = False
    payload["api_can_trigger_trading"] = False
    payload["api_can_submit_orders"] = False
    payload["api_can_start_campaign"] = False
    return payload


def _slice(*names: str) -> dict[str, Any]:
    reports = V82ReportFactory().build()
    return _safe({name.removesuffix(".json"): reports[name] for name in names})


def _route(group: str):
    async def handler() -> dict[str, Any]:
        return _slice(*REPORT_GROUPS[group])

    return handler


for _group in REPORT_GROUPS:
    router.add_api_route(f"/{_group}", _route(_group), methods=["GET"])
