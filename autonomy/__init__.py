"""Autonomous predator layer: scan -> signal -> forecast -> allocate -> risk ->
execute -> reconcile -> learn, under self-managed dynamic risk.

Dummy doctrine: fail-closed, honest status enums, and gates may only be added
or hardened. Every signal source carries a trust score that is updated only
by realized outcomes.
The only operator controls are start and stop; everything between is decided
by the system inside the risk brain's survival constraints.
"""
