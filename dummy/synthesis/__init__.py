"""DUMMY vNext structured, family-capped forecast synthesis."""

from .engine import synthesize
from .models import (
    CalibrationState,
    FamilyCapPolicy,
    SynthesisResult,
    SynthesisSource,
    SynthesisValidationError,
)

__all__ = [
    "CalibrationState",
    "FamilyCapPolicy",
    "SynthesisResult",
    "SynthesisSource",
    "SynthesisValidationError",
    "synthesize",
]
