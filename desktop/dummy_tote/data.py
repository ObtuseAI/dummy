"""Artifact reader for the Dummy Tote native desktop app.

Pure Python -- NO PySide6, NO dummy imports -- so it is unit-tested in the
normal suite and the app never depends on the trading code. It reads the same
runtime JSON artifacts the scheduled tasks already write (``runtime/autonomy``)
plus the operator switches (``configs/switches.json``), and folds them into one
structured snapshot the UI renders. Every read is fail-soft: a missing or torn
file yields ``{}`` / defaults, never an exception, so the app stays alive while
the system writes.
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path(r"C:\src\engine\dummy")
KNOWN_LEAGUES = ("mlb", "nfl", "nba", "nhl", "ncaaf", "ncaamb", "wnba")
LLM_BACKENDS = ("openrouter", "claude", "codex")

# Cross-candidate allocation (configs/allocation.json).  Mirrored here rather
# than imported: this module is deliberately free of dummy imports so the app
# runs from its own venv.  ``tests/test_tote_allocation_surface.py`` asserts
# these stay identical to ``autonomy.allocation_config``, so drift fails the
# suite rather than silently showing the operator the wrong defaults.
ALLOCATION_POLICIES = ("kelly_prorata", "proportional", "top_k")
ALLOCATION_DEFAULTS: dict[str, Any] = {
    "policy": "kelly_prorata",
    "top_k": 5,
    "min_weight": 0.25,
    "target_advantage": 0.02,
    "throttle": 1.0,
}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def league_filter_options(rows: list[dict]) -> tuple[str, ...]:
    """Year-round league filters followed by any newly observed league.

    Options are a supported-navigation roster, not evidence of current games.
    Keeping this pure lets the legacy native surface share the same honest
    behavior without importing PySide in tests.
    """
    observed = {
        str(row.get("league") or "").strip().lower()
        for row in rows
        if isinstance(row, dict) and row.get("league")
    }
    extras = sorted(observed.difference(KNOWN_LEAGUES))
    return (*KNOWN_LEAGUES, *extras)


def resolve_runtime_dir(root: Path | str | None = None) -> Path:
    """Resolve one runtime directory for the tote and its notification reader."""
    override = os.environ.get("DUMMY_RUNTIME_DIR")
    if override:
        return Path(override)
    checkout = Path(root) if root else DEFAULT_ROOT
    return checkout / "runtime" / "autonomy"

# Artifact -> freshness threshold (seconds) for the stale badge.
_FRESHNESS = {
    "heartbeat.json": 1800,
    "bet_board.json": 2400,
    "heal_status.json": 900,
    "mispricing_monitor_latest.json": 900,
    "crypto_paper_twin_latest.json": 6 * 3600,
    "vnext_shadow_status.json": 1800,
}


def _now() -> float:
    return time.time()


@dataclass
class Snapshot:
    at: float
    heartbeat: dict[str, Any] = field(default_factory=dict)
    board: dict[str, Any] = field(default_factory=dict)
    switches: dict[str, Any] = field(default_factory=dict)
    allocation: dict[str, Any] = field(default_factory=dict)
    heal: dict[str, Any] = field(default_factory=dict)
    watchdog: dict[str, Any] = field(default_factory=dict)
    vnext: dict[str, Any] = field(default_factory=dict)
    crypto: dict[str, Any] = field(default_factory=dict)
    mispricing: dict[str, Any] = field(default_factory=dict)
    plan: dict[str, Any] = field(default_factory=dict)
    session: dict[str, Any] = field(default_factory=dict)
    risk: dict[str, Any] = field(default_factory=dict)
    budget: dict[str, Any] = field(default_factory=dict)
    clv: dict[str, Any] = field(default_factory=dict)
    promotion: dict[str, Any] = field(default_factory=dict)
    readiness: dict[str, Any] = field(default_factory=dict)
    ages: dict[str, dict[str, Any]] = field(default_factory=dict)

    # -- derived KPIs the header/overview read -------------------------------

    def alive(self) -> bool:
        return bool(self.heartbeat.get("alive"))

    def last_cycle(self) -> str:
        return str(self.heartbeat.get("last_cycle_at") or "—")

    def mode(self) -> str:
        return str(self.heartbeat.get("mode") or "—")

    def connectivity_ok(self) -> bool:
        # No heal report yet -> assume ok rather than alarm.
        return bool(self.heal.get("connectivity_ok", True))

    def picks(self) -> list[dict[str, Any]]:
        top = self.board.get("top")
        return list(top) if isinstance(top, list) else []

    def pick_count(self) -> int:
        return int(self.board.get("rows") or 0)

    def top_edge(self) -> float | None:
        picks = self.picks()
        edges = [p["edge"] for p in picks if isinstance(p.get("edge"), (int, float))]
        return max(edges, key=abs) if edges else None

    def llm_state(self) -> dict[str, bool]:
        llm = self.switches.get("llm") or {}
        return {b: bool(llm.get(b)) for b in LLM_BACKENDS}

    def stale(self) -> list[str]:
        return [name for name, meta in self.ages.items() if meta.get("stale")]


class RepoData:
    """Reads the live artifacts from a dummy checkout root."""

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root else DEFAULT_ROOT
        self.runtime = resolve_runtime_dir(self.root)
        self.switches_path = self.root / "configs" / "switches.json"
        self.allocation_path = self.root / "configs" / "allocation.json"
        self._cache: dict[Path, tuple[tuple[int, int], Any]] = {}
        self._switch_lock = threading.RLock()

    def _load(self, path: Path) -> Any:
        try:
            stat = path.stat()
            signature = (stat.st_mtime_ns, stat.st_size)
            cached = self._cache.get(path)
            if cached and cached[0] == signature:
                return cached[1]
            payload = json.loads(path.read_text(encoding="utf-8"))
            self._cache[path] = (signature, payload)
            return payload
        except (OSError, ValueError, TypeError):
            cached = self._cache.get(path)
            return cached[1] if cached else {}

    def _rt(self, name: str) -> dict[str, Any]:
        data = self._load(self.runtime / name)
        return data if isinstance(data, dict) else {}

    def _age(self, name: str, payload: dict[str, Any], stamp_keys: tuple[str, ...]) -> None:
        stamp = None
        for key in stamp_keys:
            value = payload.get(key)
            if value:
                stamp = value
                break
        age = None
        if stamp:
            try:
                from datetime import datetime

                parsed = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
                age = _now() - parsed.timestamp()
            except (ValueError, TypeError):
                age = None
        threshold = _FRESHNESS.get(name)
        self._ages_out[name] = {
            "age_seconds": round(age, 1) if age is not None else None,
            "stale": age is None or (threshold is not None and age > threshold),
        }

    def snapshot(self) -> Snapshot:
        self._ages_out: dict[str, dict[str, Any]] = {}
        heartbeat = self._rt("heartbeat.json")
        board = self._rt("bet_board.json")
        heal = self._rt("heal_status.json")
        vnext = self._rt("vnext_shadow_status.json")
        crypto = self._rt("crypto_paper_twin_latest.json")
        mispricing = self._rt("mispricing_monitor_latest.json")
        switches = self._load(self.switches_path)
        switches = switches if isinstance(switches, dict) else {}

        self._age("heartbeat.json", heartbeat, ("last_cycle_at", "generated_at", "at"))
        self._age("bet_board.json", board, ("generated_at",))
        self._age("heal_status.json", heal, ("at",))
        self._age("vnext_shadow_status.json", vnext, ("at",))
        self._age("crypto_paper_twin_latest.json", crypto, ("generated_at", "at"))
        self._age("mispricing_monitor_latest.json", mispricing, ("generated_at", "at"))

        return Snapshot(
            at=_now(), heartbeat=heartbeat, board=board, switches=switches,
            allocation=self.allocation(),
            heal=heal, watchdog=self._rt("watchdog_status.json"), vnext=vnext,
            crypto=crypto, mispricing=mispricing, plan=self._rt("self_improvement_plan.json"),
            session=self._rt("session.json"), risk=self._rt("risk_state.json"),
            budget=self._rt("odds_api_budget.json"), clv=self._rt("clv_report.json"),
            promotion=self._rt("auto_promotion_state.json"),
            readiness=self._rt("readiness_report.json"), ages=self._ages_out)

    # -- allocation control (how the cycle pot is split per candidate) --------

    def allocation(self) -> dict[str, Any]:
        """Current allocation settings, with every missing key defaulted.

        Never raises and never returns a partial dict: the UI always has all
        five keys to render.
        """
        raw = self._load(self.allocation_path)
        raw = raw if isinstance(raw, dict) else {}
        out = dict(ALLOCATION_DEFAULTS)
        if raw.get("policy") in ALLOCATION_POLICIES:
            out["policy"] = raw["policy"]
        for key in ("top_k",):
            value = raw.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                out[key] = max(0, value)
        for key in ("min_weight", "target_advantage", "throttle"):
            value = raw.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                out[key] = float(value)
        out["throttle"] = _clamp(float(out["throttle"]), 0.0, 1.0)
        out["min_weight"] = _clamp(float(out["min_weight"]), 0.01, 1.0)
        return out

    def set_allocation(self, **changes: Any) -> None:
        """Update allocation settings in place, preserving untouched keys.

        ``throttle`` is clamped to [0, 1]: the operator can always shrink the
        pot from here, never enlarge it.  Enlarging is the sealed-caps
        ceremony, not a slider.
        """
        policy = changes.get("policy")
        if policy is not None and policy not in ALLOCATION_POLICIES:
            raise ValueError(f"unknown allocation policy {policy!r}")

        with self._switch_lock:
            data = self.allocation()
            for key, value in changes.items():
                if value is None:
                    continue
                if key not in ALLOCATION_DEFAULTS:
                    raise ValueError(f"unknown allocation key {key!r}")
                data[key] = value
            data["top_k"] = max(0, int(data["top_k"]))
            data["throttle"] = _clamp(float(data["throttle"]), 0.0, 1.0)
            data["min_weight"] = _clamp(float(data["min_weight"]), 0.01, 1.0)
            data["target_advantage"] = max(1e-6, float(data["target_advantage"]))

            self.allocation_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.allocation_path.with_suffix(".apptmp")
            tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
            tmp.replace(self.allocation_path)
            self._cache.pop(self.allocation_path, None)

    # -- switch control (the app writes the same file dummy_switches.py does) --

    def set_switch(self, domain: str, value: bool, key: str | None = None) -> None:
        with self._switch_lock:
            data = self._load(self.switches_path)
            data = dict(data) if isinstance(data, dict) else {}
            if domain in ("main", "crypto", "sports"):
                data[domain] = value
            elif domain == "league" and key:
                data["leagues"] = dict(data.get("leagues") or {})
                data["leagues"][key] = value
            elif domain == "llm" and key:
                data["llm"] = dict(data.get("llm") or {})
                data["llm"][key] = value
            else:
                raise ValueError(f"unknown switch {domain}/{key}")
            self.switches_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.switches_path.with_suffix(".apptmp")
            tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
            tmp.replace(self.switches_path)
            self._cache.pop(self.switches_path, None)
