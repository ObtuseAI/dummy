"""Authority lattice shared by every vNext component."""

from __future__ import annotations

from enum import IntEnum


class Authority(IntEnum):
    """Monotonic authority classes.

    The integer values are deliberately spaced so future non-capital classes
    can be inserted without changing the ordering.  A component may exercise
    an authority only when its grant is greater than or equal to that class.
    """

    OBSERVE = 10
    MODEL = 20
    FORECAST = 30
    CHALLENGE = 40
    SIMULATE = 50
    RECOMMEND = 60
    PAPER_ALLOCATE = 70
    LIVE_PROPOSE = 80
    EXECUTE = 90

    def allows(self, required: Authority) -> bool:
        """Return whether this grant permits the required action."""

        return self >= required


RESEARCH_AUTHORITY_CEILING = Authority.SIMULATE
CAPITAL_AUTHORITIES = frozenset({Authority.LIVE_PROPOSE, Authority.EXECUTE})


class AuthorityViolation(PermissionError):
    """Raised when a component attempts to exceed its authority."""


def can_delegate(grant: Authority, delegated: Authority) -> bool:
    """Authority may flow downward, never upward."""

    return grant.allows(delegated)


def assert_authority_at_most(
    authority: Authority,
    ceiling: Authority,
    *,
    component: str,
) -> None:
    """Fail closed when a component exceeds its declared ceiling."""

    if authority > ceiling:
        raise AuthorityViolation(
            f"{component} requested {authority.name}; ceiling is {ceiling.name}"
        )
