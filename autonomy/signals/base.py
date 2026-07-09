"""Signal source protocol + registry."""
from __future__ import annotations

from typing import Iterable, Protocol

from autonomy.ontology import MarketView, Signal


class SignalSource(Protocol):
    name: str

    def applicable(self, market: MarketView) -> bool: ...

    def generate(self, market: MarketView) -> Signal | None: ...


class SourceRegistry:
    def __init__(self) -> None:
        self._sources: list[SignalSource] = []

    def register(self, source: SignalSource) -> None:
        self._sources.append(source)

    def sources(self) -> list[SignalSource]:
        return list(self._sources)

    def on_cycle_start(self) -> None:
        """Give sources a once-per-cycle hook (cache reset, incremental
        retrain). A failing hook never stalls the cycle."""
        for source in self._sources:
            hook = getattr(source, "on_cycle_start", None)
            if callable(hook):
                try:
                    hook()
                except Exception:
                    continue

    def signals_for(self, market: MarketView) -> Iterable[Signal]:
        for source in self._sources:
            try:
                if not source.applicable(market):
                    continue
                signal = source.generate(market)
            except Exception:
                # A failing source must never stall the loop; trust decay is
                # handled by the learner from its absence/quality, not here.
                continue
            if signal is not None:
                yield signal
