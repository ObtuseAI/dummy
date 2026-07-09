from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v57.reports import REPORT_GROUPS, V57ReportFactory

router = APIRouter(prefix="/api/v57", tags=["v57"])


def _reports() -> dict[str, dict[str, Any]]:
    return V57ReportFactory().build()


def _safe(payload: dict[str, Any]) -> dict[str, Any]:
    payload["live_submit_disabled"] = True
    payload["caps_unchanged"] = True
    payload["execution_bridge_present"] = False
    payload["api_can_trigger_probes"] = False
    payload["api_can_trigger_trading"] = False
    payload["api_can_create_approval_file"] = False
    payload["api_can_create_quarantine_artifacts"] = False
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
