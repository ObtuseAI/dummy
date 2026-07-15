"""Immutable archive of external evolution-evaluation reports."""

from __future__ import annotations

from typing import Any, Mapping

from dummy.world_model.models import canonical_json, digest_json, freeze_json, thaw_json


class EvolutionArchive:
    def __init__(self) -> None:
        self._reports: dict[str, Any] = {}

    def append(self, report: Mapping[str, Any]) -> str:
        report_id = str(report.get("family_report_id", "")).strip()
        if not report_id or report_id != digest_json(
            {key: value for key, value in report.items() if key != "family_report_id"}
        ):
            raise ValueError("evolution archive requires a valid family report ID")
        frozen = freeze_json(report)
        existing = self._reports.get(report_id)
        if existing is not None and canonical_json(existing) != canonical_json(frozen):
            raise ValueError("evolution report ID collision has different content")
        self._reports[report_id] = frozen
        return report_id

    def reports(self) -> tuple[dict[str, Any], ...]:
        return tuple(thaw_json(self._reports[key]) for key in sorted(self._reports))

    def snapshot(self) -> dict[str, Any]:
        body = {
            "schema_version": 1,
            "report_count": len(self._reports),
            "reports": list(self.reports()),
            "append_only": True,
        }
        body["archive_id"] = digest_json(body)
        return body


__all__ = ["EvolutionArchive"]
