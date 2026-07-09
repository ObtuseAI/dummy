"""Signal sources. Each source is registered with a trust weight that only
realized outcomes may move (Blunder inflow doctrine)."""
from autonomy.signals.base import SignalSource, SourceRegistry

__all__ = ["SignalSource", "SourceRegistry"]
