"""Truth-preserving paper-twin dashboard metrics and local scheduler controls."""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


PAPER_TASK_NAME = "DummyCryptoPaperTwin"
PAPER_CONTROL_HEADER = "paper-twin-scheduler-v1"
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _json_object(value: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _age_seconds(value: Any) -> float | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return round(max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds()), 1)
    except (TypeError, ValueError):
        return None


def _task_script(task_name: str) -> str:
    safe_name = task_name.replace("'", "''")
    return (
        f"$task=Get-ScheduledTask -TaskName '{safe_name}' -ErrorAction Stop;"
        f"$info=Get-ScheduledTaskInfo -TaskName '{safe_name}' -ErrorAction Stop;"
        "$action=$task.Actions|Select-Object -First 1;"
        "[pscustomobject]@{"
        "state=$task.State.ToString();enabled=($task.State.ToString() -ne 'Disabled');"
        "last_run_time=$info.LastRunTime.ToString('o');"
        "last_result=$info.LastTaskResult;next_run_time=$info.NextRunTime.ToString('o');"
        "execute=$action.Execute;arguments=$action.Arguments;"
        "working_directory=$action.WorkingDirectory;"
        "execution_time_limit=$task.Settings.ExecutionTimeLimit;"
        "start_when_available=$task.Settings.StartWhenAvailable;"
        "multiple_instances=$task.Settings.MultipleInstances.ToString()"
        "}|ConvertTo-Json -Compress"
    )


def scheduled_task_status(
    task_name: str = PAPER_TASK_NAME,
    *,
    runner: CommandRunner = subprocess.run,
) -> dict[str, Any]:
    """Read the fixed Windows paper scheduler without exposing a command surface."""
    if os.name != "nt":
        return {
            "task_name": task_name,
            "supported": False,
            "enabled": False,
            "state": "UNSUPPORTED_PLATFORM",
            "healthy": False,
        }
    try:
        completed = runner(
            [
                "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                _task_script(task_name),
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError("scheduled task query failed")
        payload = json.loads(completed.stdout.strip())
        if not isinstance(payload, dict):
            raise ValueError("scheduled task query returned invalid JSON")
    except (OSError, RuntimeError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return {
            "task_name": task_name,
            "supported": True,
            "enabled": False,
            "state": "UNAVAILABLE",
            "healthy": False,
            "error": type(exc).__name__,
        }
    result = int(payload.get("last_result") or 0)
    state = str(payload.get("state") or "UNKNOWN")
    return {
        "task_name": task_name,
        "supported": True,
        "enabled": bool(payload.get("enabled")),
        "state": state,
        "running": state == "Running",
        "healthy": state in {"Ready", "Running"} and result in {0, 267009},
        "last_run_time": payload.get("last_run_time"),
        "last_result": result,
        "next_run_time": payload.get("next_run_time"),
        "execute": payload.get("execute"),
        "arguments": payload.get("arguments"),
        "working_directory": payload.get("working_directory"),
        "execution_time_limit": payload.get("execution_time_limit"),
        "start_when_available": bool(payload.get("start_when_available")),
        "multiple_instances": payload.get("multiple_instances"),
        "control_scope": "paper_scheduler_only",
        "live_execution_authority": False,
        "capital_authority": False,
    }


def control_paper_scheduler(
    action: str,
    task_name: str = PAPER_TASK_NAME,
    *,
    runner: CommandRunner = subprocess.run,
) -> dict[str, Any]:
    """Enable/start or pause future paper cycles; never touch live execution."""
    normalized = str(action).strip().lower()
    if normalized not in {"start", "stop"}:
        raise ValueError("action must be start or stop")
    if os.name != "nt":
        return {
            "ok": False,
            "action": normalized,
            "error": "UNSUPPORTED_PLATFORM",
            "live_execution_authority": False,
            "capital_authority": False,
        }
    safe_name = task_name.replace("'", "''")
    if normalized == "start":
        script = (
            f"Enable-ScheduledTask -TaskName '{safe_name}' -ErrorAction Stop|Out-Null;"
            f"Start-ScheduledTask -TaskName '{safe_name}' -ErrorAction Stop"
        )
        message = "Paper scheduler enabled; an immediate cycle was requested."
    else:
        script = f"Disable-ScheduledTask -TaskName '{safe_name}' -ErrorAction Stop"
        message = "Future paper cycles paused; an in-flight cycle may finish cleanly."
    completed = runner(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if completed.returncode != 0:
        return {
            "ok": False,
            "action": normalized,
            "error": "SCHEDULED_TASK_CONTROL_FAILED",
            "message": (completed.stderr or "").strip()[-500:],
            "live_execution_authority": False,
            "capital_authority": False,
        }
    return {
        "ok": True,
        "action": normalized,
        "message": message,
        "control_scope": "paper_scheduler_only",
        "live_execution_authority": False,
        "capital_authority": False,
    }


def _trade_row(row: sqlite3.Row) -> dict[str, Any]:
    snapshot = _json_object(row["market_snapshot_json"])
    features = _json_object(row["features_json"])
    target = features.get("price_target") or features.get("target_selection", {}).get(
        "selected_target"
    ) or snapshot.get("price_target") or {}
    return {
        "trade_id": row["trade_id"],
        "strategy": row["strategy"],
        "vertical": row["vertical"],
        "asset": row["asset"],
        "timeframe": row["timeframe"],
        "ticker": row["ticker"],
        "target": target,
        "side": str(row["side"]).upper(),
        "created_at": row["created_at"],
        "close_time": row["close_time"],
        "status": row["status"],
        "probability_yes": row["probability_yes"],
        "market_probability": row["market_probability"],
        "uncertainty": row["uncertainty"],
        "edge_cents": row["edge_cents"],
        "conservative_ev_cents": row["conservative_ev_cents"],
        "entry_price_cents": row["taker_price_cents"],
        "fee_cents": row["taker_fee_cents"],
        "paper_cost_cents": int(row["taker_price_cents"]) + int(row["taker_fee_cents"]),
        "maker_status": row["maker_status"],
        "maker_price_cents": row["maker_price_cents"],
        "result_yes": row["result_yes"],
        "settled_at": row["settled_at"],
        "taker_pnl_cents": row["taker_pnl_cents"],
        "maker_pnl_cents": row["maker_pnl_cents"],
        "explanation": row["explanation"],
    }


def _flatten_lanes(summary: dict[str, Any]) -> list[dict[str, Any]]:
    cohorts = summary.get("cohorts") or {}
    if not cohorts and summary.get("lanes"):
        cohorts = {"CRYPTO": summary["lanes"]}
    output: list[dict[str, Any]] = []
    for vertical, timeframes in cohorts.items():
        if not isinstance(timeframes, dict):
            continue
        for timeframe, strategies in timeframes.items():
            if not isinstance(strategies, dict):
                continue
            for strategy, metrics in strategies.items():
                if not isinstance(metrics, dict):
                    continue
                output.append({
                    "vertical": vertical,
                    "timeframe": timeframe,
                    "strategy": strategy,
                    **metrics,
                })
    return sorted(
        output,
        key=lambda row: (
            str(row.get("vertical")), str(row.get("timeframe")),
            str(row.get("strategy")),
        ),
    )


def assemble_paper_dashboard(runtime_dir: Path) -> dict[str, Any]:
    """Read compact scheduler/report data plus the paper ledger in query-only mode."""
    summary = _read_json(runtime_dir / "crypto_paper_twin_latest.json")
    result: dict[str, Any] = {
        "paper_mode": summary.get("paper_mode") or "LIVE_PUBLIC_READ_ONLY_SIMULATION",
        "latest_cycle": {
            key: summary.get(key) for key in (
                "cycle_id", "started_at", "completed_at", "status", "markets_seen",
                "observations_written", "trades_opened", "settlements_recorded", "errors",
            )
        },
        "freshness_seconds": _age_seconds(summary.get("completed_at")),
        "target_candidate_counts": summary.get("target_candidate_counts") or {},
        "hourly_calibration": summary.get("hourly_calibration") or {},
        "forced_crypto_coverage": summary.get("forced_crypto_coverage") or {},
        "throughput": summary.get("throughput") or {},
        "lanes": _flatten_lanes(summary),
        "weaknesses": list(summary.get("weaknesses") or [])[:20],
        "active_trades": [],
        "recent_settlements": [],
        "recent_decisions": [],
        "pnl_curve": [],
        "metrics": {
            "trades": 0,
            "open_trades": 0,
            "settled_trades": 0,
            "wins": 0,
            "win_rate": None,
            "quote_simulated_net_pnl_cents": 0,
            "maker_witness_net_pnl_cents": 0,
            "open_paper_cost_cents": 0,
            "unrealized_pnl_cents": None,
        },
        "pnl_truth": {
            "quote_simulated": "one-contract live top-ask paper entries; not witnessed fills",
            "maker_witness": "public-print execution research only; not readiness or capital evidence",
            "unrealized": "not shown without a fresh executable mark",
        },
        "authority": summary.get("authority") or {
            "broker_contacted": False,
            "execution_authority": False,
            "capital_authority": False,
        },
    }
    database = (runtime_dir / "crypto_paper_twin.db").resolve()
    if not database.exists():
        result["ledger_status"] = "MISSING"
        return result
    try:
        connection = sqlite3.connect(
            f"file:{database.as_posix()}?mode=ro", uri=True, timeout=5,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        aggregate = connection.execute(
            "SELECT COUNT(*) trades,"
            "SUM(CASE WHEN status='OPEN' THEN 1 ELSE 0 END) open_trades,"
            "SUM(CASE WHEN status='SETTLED' THEN 1 ELSE 0 END) settled_trades,"
            "SUM(CASE WHEN status='SETTLED' AND taker_pnl_cents>0 THEN 1 ELSE 0 END) wins,"
            "COALESCE(SUM(CASE WHEN status='SETTLED' THEN taker_pnl_cents END),0) taker_pnl,"
            "COALESCE(SUM(CASE WHEN status='SETTLED' THEN maker_pnl_cents END),0) maker_pnl,"
            "COALESCE(SUM(CASE WHEN status='OPEN' THEN taker_price_cents+taker_fee_cents END),0) open_cost "
            "FROM trades"
        ).fetchone()
        settled = int(aggregate["settled_trades"] or 0)
        wins = int(aggregate["wins"] or 0)
        result["metrics"] = {
            "trades": int(aggregate["trades"] or 0),
            "open_trades": int(aggregate["open_trades"] or 0),
            "settled_trades": settled,
            "wins": wins,
            "win_rate": round(wins / settled, 6) if settled else None,
            "quote_simulated_net_pnl_cents": int(aggregate["taker_pnl"] or 0),
            "maker_witness_net_pnl_cents": int(aggregate["maker_pnl"] or 0),
            "open_paper_cost_cents": int(aggregate["open_cost"] or 0),
            "unrealized_pnl_cents": None,
        }
        columns = (
            "trade_id,strategy,vertical,timeframe,asset,ticker,side,created_at,close_time,"
            "probability_yes,market_probability,uncertainty,edge_cents,conservative_ev_cents,"
            "taker_price_cents,taker_fee_cents,status,result_yes,settled_at,taker_pnl_cents,"
            "explanation,features_json,market_snapshot_json,maker_status,maker_price_cents,"
            "maker_pnl_cents"
        )
        result["active_trades"] = [
            _trade_row(row) for row in connection.execute(
                f"SELECT {columns} FROM trades WHERE status='OPEN' "  # noqa: S608
                "ORDER BY close_time,created_at LIMIT 50"
            )
        ]
        result["recent_settlements"] = [
            _trade_row(row) for row in connection.execute(
                f"SELECT {columns} FROM trades WHERE status='SETTLED' "  # noqa: S608
                "ORDER BY settled_at DESC,trade_id DESC LIMIT 25"
            )
        ]
        cumulative = 0
        curve: list[dict[str, Any]] = []
        for row in connection.execute(
            "SELECT settled_at,taker_pnl_cents FROM trades WHERE status='SETTLED' "
            "AND taker_pnl_cents IS NOT NULL ORDER BY settled_at,trade_id"
        ):
            cumulative += int(row["taker_pnl_cents"])
            curve.append({"at": row["settled_at"], "pnl_cents": cumulative})
        result["pnl_curve"] = curve[-200:]
        result["recent_decisions"] = [
            dict(row) for row in connection.execute(
                "SELECT created_at,strategy,vertical,timeframe,asset,action,ticker,explanation "
                "FROM observations ORDER BY rowid DESC LIMIT 25"
            )
        ]
        result["ledger_status"] = "QUERY_ONLY_OK"
    except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
        result["ledger_status"] = "UNAVAILABLE"
        result["ledger_error"] = type(exc).__name__
    finally:
        if "connection" in locals():
            connection.close()
    return result
