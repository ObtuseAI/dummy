"""Compact dashboard state for the continuous sports paper twin."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SPORTS_TASK_NAME = "DummySportsSimulation"


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _age_seconds(value: Any) -> float | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return round(max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds()), 1)
    except (TypeError, ValueError):
        return None


def assemble_sports_dashboard(runtime_dir: Path) -> dict[str, Any]:
    state = _load(runtime_dir / "sports_simulation_latest.json")
    summary = state.get("paper_decision_summary") or {}
    coverage = state.get("forced_coverage") or {}
    return {
        "paper_mode": "LIVE_PUBLIC_READ_ONLY_SIMULATION",
        "latest_cycle": {
            key: state.get(key) for key in (
                "cycle_id", "started_at", "completed_at", "status", "markets_seen",
                "observations_written", "paper_picks", "policy_paper_trades_recorded",
                "forced_paper_trades_recorded", "settlements_recorded",
                "paper_settlements_recorded", "errors",
            )
        },
        "freshness_seconds": _age_seconds(state.get("completed_at")),
        "metrics": {
            "decisions": int(summary.get("decisions") or 0),
            "open_trades": int(summary.get("open_decisions") or 0),
            "settled_trades": int(summary.get("settled_decisions") or 0),
            "wins": int(summary.get("wins") or 0),
            "win_rate": summary.get("win_rate"),
            "net_pnl_cents": int(summary.get("net_pnl_cents") or 0),
        },
        "lane_summary": list(summary.get("lanes") or []),
        "coverage": coverage,
        "active_trades": list(state.get("active_paper_trades") or []),
        "recent_settlements": list(state.get("recent_paper_settlements") or []),
        "authority": state.get("authority") or {
            "broker_contacted": False,
            "execution_authority": False,
            "capital_authority": False,
            "forced_coverage_counts_toward_promotion": False,
        },
        "evidence_boundary": {
            "forced_coverage": "diagnostic only",
            "real_listed_markets_only": True,
            "fabricated_trades": False,
            "counts_toward_promotion": False,
        },
    }
