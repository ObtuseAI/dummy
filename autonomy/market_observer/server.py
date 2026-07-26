"""Minimal dependency-free MCP-compatible stdio server.

The implementation intentionally exposes only seven read-only, facts-only
tools. It does not import the executor, firewall, broker clients, operator
configuration, browser automation, or TradingView.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, TextIO

from autonomy.market_observer.contracts import (
    ALLOWED_ASSETS,
    ALLOWED_TIMEFRAMES,
    ObservationEnvelope,
)
from autonomy.market_observer.runtime import SingleRunLock
from autonomy.market_observer.service import MarketObserver

SERVER_NAME = "dummy-market-observer"
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2025-06-18"

_COMMON_PROPERTIES = {
    "asset": {
        "type": "string",
        "enum": sorted(ALLOWED_ASSETS),
        "description": "Crypto asset symbol.",
    },
    "timeframe": {
        "type": "string",
        "enum": sorted(ALLOWED_TIMEFRAMES),
        "description": "Closed-candle timeframe.",
    },
    "limit": {
        "type": "integer",
        "minimum": 1,
        "maximum": 200,
        "default": 120,
        "description": "Maximum number of closed bars.",
    },
}


def _tool(
    name: str,
    description: str,
    *,
    properties: tuple[str, ...] = ("asset", "timeframe", "limit"),
    required: tuple[str, ...] = ("asset", "timeframe"),
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": {key: _COMMON_PROPERTIES[key] for key in properties},
            "required": list(required),
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    }


TOOLS: tuple[dict[str, Any], ...] = (
    _tool("get_candles", "Fetch closed public OHLCV bars with point-in-time provenance."),
    _tool(
        "get_market_snapshot",
        "Return latest public price/volume facts and window change; no forecast.",
    ),
    _tool(
        "compute_indicators",
        "Compute deterministic local indicators over the same frozen closed bars.",
    ),
    _tool(
        "detect_candlestick_patterns",
        "Detect named local candlestick patterns over closed bars; no trade advice.",
    ),
    _tool(
        "get_chart_bundle",
        "Return candles, local indicators, and pattern markers for visualization.",
    ),
    _tool(
        "get_network_metrics",
        "Return contract-reviewed public network facts, or explicit UNAVAILABLE.",
        properties=("asset",),
        required=("asset",),
    ),
    _tool(
        "source_health",
        "Inspect immutable local success/failure observation pointers without network I/O.",
        properties=("asset", "timeframe"),
        required=("asset", "timeframe"),
    ),
)
TOOL_NAMES = frozenset(tool["name"] for tool in TOOLS)


def _validated_arguments(name: str, arguments: Any) -> dict[str, Any]:
    if name not in TOOL_NAMES:
        raise ValueError("unknown observer tool")
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise ValueError("tool arguments must be an object")
    allowed = {"asset"}
    required = {"asset"}
    if name != "get_network_metrics":
        allowed.add("timeframe")
        required.add("timeframe")
    if name not in {"get_network_metrics", "source_health"}:
        allowed.add("limit")
    extras = set(arguments) - allowed
    if extras:
        raise ValueError(f"unexpected tool arguments: {sorted(extras)}")
    missing = required - set(arguments)
    if missing:
        raise ValueError(f"missing tool arguments: {sorted(missing)}")
    asset = arguments["asset"]
    timeframe = arguments.get("timeframe", "1d")
    if not isinstance(asset, str) or asset.upper() not in ALLOWED_ASSETS:
        raise ValueError("asset must be BTC, ETH, or SOL")
    if not isinstance(timeframe, str) or timeframe not in ALLOWED_TIMEFRAMES:
        raise ValueError("unsupported timeframe")
    limit = arguments.get("limit", 120)
    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or not 1 <= limit <= 200
    ):
        raise ValueError("limit must be an integer from 1 through 200")
    validated = {"asset": asset.upper(), "timeframe": timeframe, "limit": limit}
    return validated


class ObserverToolRouter:
    def __init__(self, observer: MarketObserver) -> None:
        self.observer = observer

    def call(self, name: str, arguments: Any) -> tuple[ObservationEnvelope, bool]:
        raw_arguments = arguments if isinstance(arguments, dict) else {}
        try:
            args = _validated_arguments(name, arguments)
            if name == "get_candles":
                result = self.observer.get_candles(**args)
            elif name == "get_market_snapshot":
                result = self.observer.get_market_snapshot(**args)
            elif name == "compute_indicators":
                result = self.observer.compute_indicators(**args)
            elif name == "detect_candlestick_patterns":
                result = self.observer.detect_candlestick_patterns(**args)
            elif name == "get_chart_bundle":
                result = self.observer.get_chart_bundle(**args)
            elif name == "get_network_metrics":
                result = self.observer.get_network_metrics(args["asset"])
            elif name == "source_health":
                result = self.observer.source_health(
                    args["asset"],
                    args["timeframe"],
                )
            else:  # guarded by _validated_arguments
                raise ValueError("unknown observer tool")
            return result, False
        except Exception as exc:
            failure = self.observer.record_failure(name, raw_arguments, exc)
            return failure, True


def _result(request_id: Any, value: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": value}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def handle_message(
    message: Any,
    router: ObserverToolRouter,
) -> dict[str, Any] | None:
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _error(None, -32600, "Invalid Request")
    request_id = message.get("id")
    method = message.get("method")
    params = message.get("params") or {}
    if method in {"notifications/initialized", "notifications/cancelled"}:
        return None
    if method == "initialize":
        return _result(
            request_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": (
                    "Read-only public crypto observations. Facts and chart data only; "
                    "all execution, order, allocation, and promotion authority is false."
                ),
            },
        )
    if method == "ping":
        return _result(request_id, {})
    if method == "tools/list":
        return _result(request_id, {"tools": list(TOOLS)})
    if method == "tools/call":
        if not isinstance(params, dict):
            return _error(request_id, -32602, "Invalid params")
        name = params.get("name")
        if not isinstance(name, str):
            return _error(request_id, -32602, "Invalid params")
        envelope, is_error = router.call(name, params.get("arguments"))
        structured = envelope.to_dict()
        return _result(
            request_id,
            {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            structured,
                            sort_keys=True,
                            separators=(",", ":"),
                            allow_nan=False,
                        ),
                    }
                ],
                "structuredContent": structured,
                "isError": is_error,
            },
        )
    return _error(request_id, -32601, "Method not found")


def _serve_stdio(
    input_stream: TextIO,
    output_stream: TextIO,
    router: ObserverToolRouter,
) -> int:
    for line in input_stream:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            response = handle_message(message, router)
        except json.JSONDecodeError:
            response = _error(None, -32700, "Parse error")
        except Exception:
            # Protocol-level failures disclose no traceback or environment data.
            response = _error(None, -32603, "Internal error")
        if response is not None:
            output_stream.write(
                json.dumps(
                    response,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
                + "\n"
            )
            output_stream.flush()
    return 0


def run_stdio(
    *,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
    observer: MarketObserver | None = None,
) -> int:
    input_stream = input_stream or sys.stdin
    output_stream = output_stream or sys.stdout
    configured_root = Path(
        os.environ.get(
            "DUMMY_MARKET_OBSERVER_ROOT",
            "artifacts/dummy/market_observer",
        )
    )
    selected_observer = observer or MarketObserver(artifact_root=configured_root)
    router = ObserverToolRouter(selected_observer)
    with SingleRunLock(selected_observer.store.root / "observer.lock"):
        return _serve_stdio(input_stream, output_stream, router)
