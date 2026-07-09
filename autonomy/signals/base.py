"""Signal source protocol + registry with self-healing circuit breakers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Protocol

from autonomy.ontology import MarketView, Signal

# Trip after this many consecutive generate() exceptions; sit out this many
# cycles, then retry. A dead upstream API stops burning the cycle budget, but
# nothing is ever permanently disabled — recovery is one clean success away.
BREAKER_THRESHOLD = 5
QUARANTINE_CYCLES = 3


class SignalSource(Protocol):
    name: str

    def applicable(self, market: MarketView) -> bool: ...

    def generate(self, market: MarketView) -> Signal | None: ...


class SourceRegistry:
    def __init__(self, health_path: Path | str | None = None) -> None:
        self._sources: list[SignalSource] = []
        self.health_path = Path(health_path) if health_path else None
        # source -> {"fails": consecutive exceptions, "quarantine": cycles left}
        self._health: dict[str, dict[str, int]] = {}
        if self.health_path and self.health_path.exists():
            try:
                self._health = {
                    k: {"fails": int(v.get("fails", 0)), "quarantine": int(v.get("quarantine", 0))}
                    for k, v in json.loads(self.health_path.read_text(encoding="utf-8")).items()
                }
            except Exception:
                self._health = {}

    def register(self, source: SignalSource) -> None:
        self._sources.append(source)

    def sources(self) -> list[SignalSource]:
        return list(self._sources)

    def source_health(self) -> dict[str, dict[str, int]]:
        return {k: dict(v) for k, v in self._health.items()}

    def _save_health(self) -> None:
        if self.health_path is None:
            return
        try:
            self.health_path.parent.mkdir(parents=True, exist_ok=True)
            self.health_path.write_text(json.dumps(self._health, indent=2, sort_keys=True),
                                        encoding="utf-8")
        except Exception:
            pass  # health persistence is best-effort, never load-bearing

    def _entry(self, name: str) -> dict[str, int]:
        return self._health.setdefault(name, {"fails": 0, "quarantine": 0})

    def on_cycle_start(self) -> None:
        """Once-per-cycle hooks + quarantine countdown. Failures never stall."""
        for entry in self._health.values():
            if entry["quarantine"] > 0:
                entry["quarantine"] -= 1
        self._save_health()
        for source in self._sources:
            if self._entry(source.name)["quarantine"] > 0:
                continue  # a quarantined source's hook is skipped too
            hook = getattr(source, "on_cycle_start", None)
            if callable(hook):
                try:
                    hook()
                except Exception:
                    continue

    def signals_for(self, market: MarketView) -> Iterable[Signal]:
        for source in self._sources:
            entry = self._entry(source.name)
            if entry["quarantine"] > 0:
                continue
            try:
                if not source.applicable(market):
                    continue
                signal = source.generate(market)
            except Exception:
                # Eat the error, count it, and trip the breaker on a streak:
                # the source sits out a few cycles instead of failing on
                # every market of every sweep.
                entry["fails"] += 1
                if entry["fails"] >= BREAKER_THRESHOLD:
                    entry["quarantine"] = QUARANTINE_CYCLES
                    entry["fails"] = 0
                    self._save_health()
                continue
            if entry["fails"]:
                entry["fails"] = 0
                self._save_health()
            if signal is not None:
                yield signal
