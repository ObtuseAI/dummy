from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v52.reports import REPORT_GROUPS, V52ReportFactory

router = APIRouter(prefix="/api/v52", tags=["v52"])


def _reports() -> dict[str, dict[str, Any]]:
    return V52ReportFactory().build()


def _safe(payload: dict[str, Any]) -> dict[str, Any]:
    payload["live_submit_disabled"] = True
    payload["caps_unchanged"] = True
    payload["execution_bridge_present"] = False
    payload["api_can_trigger_probes"] = False
    payload["api_can_trigger_trading"] = False
    return payload


def _slice(*names: str) -> dict[str, Any]:
    reports = _reports()
    return _safe({name.removesuffix(".json"): reports[name] for name in names})


def _route(group: str):
    async def handler() -> dict[str, Any]:
        return _slice(*REPORT_GROUPS[group])

    return handler


for _group in REPORT_GROUPS:
    router.add_api_route(f"/{_group}", _route(_group), methods=["GET"])
