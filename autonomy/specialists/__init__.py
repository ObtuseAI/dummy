"""Council of specialists: per-vertical subagents behind a uniform protocol."""
from autonomy.specialists.base import Specialist, SpecialistHealth, SpecialistRegistry
from autonomy.specialists.factory import build_specialist_registry

__all__ = [
    "Specialist",
    "SpecialistHealth",
    "SpecialistRegistry",
    "build_specialist_registry",
]
