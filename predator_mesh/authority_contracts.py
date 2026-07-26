"""Stable integrity constants used by read-only staged-gate reports.

The values live in the authority modules that own them.  This compatibility
surface keeps current code from importing a historical ``predator_mesh.vNN``
snapshot merely to read those constants.
"""

from __future__ import annotations

from core.caps_authority import PROTECTED_CAPS_SHA256
from core.proof_authority import EXPECTED_LIVE_SUBMIT_DISABLED_HASH

CAPS_HASH = PROTECTED_CAPS_SHA256
LIVE_SUBMIT_HASH = EXPECTED_LIVE_SUBMIT_DISABLED_HASH

__all__ = ["CAPS_HASH", "LIVE_SUBMIT_HASH"]
