"""Synthesis: turn movement + steam + dispersion + public-lean into one
sharp/public read per game side.

The core inference is reverse line movement (RLM). The public piles onto the
predictable side (favorite / brand / over); its ticket volume alone would push
the line toward it. So when the line instead moves TOWARD the side the public
is off, ticket money is being overridden by heavier, sharper money -- that is
the sharp side. From there:

  * sharp_side  -- the side the smart money backed (the non-public side a
                   confirmed move ran to);
  * trap        -- a heavy public lean the line refuses to confirm (flat, or
                   moving against the public) is books shading the public: fade
                   the public side;
  * dog value   -- when the sharp side is the underdog, that is the profitable
                   contrarian dog the operator is hunting.

Pure function; the signal (autonomy/signals/market_pressure.py) feeds it and
turns ``prob_adjustment`` into a capped, challenger-only nudge.
"""
from __future__ import annotations

from dataclasses import dataclass

from autonomy.market_pressure.dispersion import DispersionRead
from autonomy.market_pressure.public_lean import PublicLeanRead
from autonomy.market_pressure.steam import SteamRead

# A public-lean gap this wide is a genuine public side (else it's a coin-flip
# crowd and "fade the public" is meaningless).
TRAP_PUBLIC_GAP = 0.20
# Hard cap on the probability nudge -- this is a challenger hint, not a model.
ADJ_CAP = 0.04


@dataclass(frozen=True)
class MarketPressureRead:
    has_read: bool
    subject_side: str
    public_side: str | None
    sharp_side: str | None
    reverse_line_movement: bool
    steam_direction: int              # +1 line toward subject, -1 toward opponent, 0 none
    steam_originator: str | None
    soft_book: str | None
    soft_offset: float | None
    public_gap: float
    trap_flag: bool
    dog_value_flag: bool
    prob_adjustment: float            # signed nudge to apply to P(subject)
    confidence: float
    rationale: str

    def as_dict(self) -> dict:
        return {
            "has_read": self.has_read,
            "subject_side": self.subject_side,
            "public_side": self.public_side,
            "sharp_side": self.sharp_side,
            "reverse_line_movement": self.reverse_line_movement,
            "steam_direction": self.steam_direction,
            "steam_originator": self.steam_originator,
            "soft_book": self.soft_book,
            "soft_offset": self.soft_offset,
            "public_gap": round(self.public_gap, 4),
            "trap_flag": self.trap_flag,
            "dog_value_flag": self.dog_value_flag,
            "prob_adjustment": round(self.prob_adjustment, 4),
            "confidence": round(self.confidence, 3),
        }


def _no_read(subject_side: str) -> MarketPressureRead:
    return MarketPressureRead(
        has_read=False, subject_side=subject_side, public_side=None, sharp_side=None,
        reverse_line_movement=False, steam_direction=0, steam_originator=None,
        soft_book=None, soft_offset=None, public_gap=0.0, trap_flag=False,
        dog_value_flag=False, prob_adjustment=0.0, confidence=0.0,
        rationale="no market-pressure read")


def synthesize_pressure(
    *,
    subject_side: str,
    opponent_side: str,
    subject_devig: float | None,
    subject_lean: PublicLeanRead,
    opponent_lean: PublicLeanRead,
    steam: SteamRead,
    dispersion: DispersionRead,
) -> MarketPressureRead:
    """Combine the reads for ONE game (from the subject's perspective).

    ``steam`` is the subject side's cross-book steam: ``direction`` +1 means
    the subject's number moved up (money toward the subject), -1 toward the
    opponent. Fail-closed: with neither a steam signal nor a public side there
    is nothing to say."""
    public_gap = abs(subject_lean.lean - opponent_lean.lean)
    public_side = (subject_side if subject_lean.lean >= opponent_lean.lean
                   else opponent_side) if public_gap > 1e-6 else None

    # Which side did a CONFIRMED move run to?
    line_toward: str | None = None
    if steam.is_steam and steam.direction != 0:
        line_toward = subject_side if steam.direction > 0 else opponent_side

    if line_toward is None and public_side is None:
        return _no_read(subject_side)

    # Reverse line movement: a confirmed move to the NON-public side.
    rlm = bool(line_toward and public_side and line_toward != public_side
               and public_gap >= TRAP_PUBLIC_GAP)

    sharp_side: str | None = None
    if rlm:
        sharp_side = line_toward
    elif line_toward and (public_side is None or line_toward != public_side):
        # A move to a non-public (or no-strong-public) side is still sharp-ish.
        sharp_side = line_toward

    # Trap: a strong public side the line moved AGAINST -- i.e. confirmed
    # reverse line movement. A merely flat line on a public favorite is the
    # normal state, not a trap; distinguishing "flat = sharp resistance" from
    # "flat = quiet" needs ticket volume, which arrives with Wave-31's scraped
    # splits. Until then the only evidence-backed trap is a reverse move.
    trap_flag = rlm

    # Dog value: the sharp side is the underdog.
    dog_value_flag = bool(
        sharp_side is not None and subject_devig is not None and (
            (sharp_side == subject_side and subject_devig < 0.5)
            or (sharp_side == opponent_side and subject_devig >= 0.5)
        )
    )

    # Capped nudge toward the sharp side, scaled by move size and public gap.
    adjustment = 0.0
    confidence = 0.0
    if sharp_side is not None:
        strength = min(1.0, abs(steam.magnitude) / 0.03) if steam.is_steam else 0.4
        gap_weight = min(1.0, public_gap / 0.4) if rlm else 0.5
        confidence = round(0.5 * strength + 0.5 * gap_weight, 3)
        magnitude = min(ADJ_CAP, ADJ_CAP * confidence)
        adjustment = magnitude if sharp_side == subject_side else -magnitude

    bits = []
    if public_side:
        bits.append(f"public on {public_side} (gap {public_gap:.2f})")
    if sharp_side:
        bits.append(f"sharp on {sharp_side}" + (" [RLM]" if rlm else ""))
    if trap_flag:
        bits.append(f"trap: fade {public_side}")
    if dog_value_flag:
        bits.append(f"dog value on {sharp_side}")
    if dispersion.is_soft_outlier and dispersion.outlier_book:
        bits.append(f"soft {dispersion.outlier_book}")
    rationale = "; ".join(bits) or "no actionable pressure"

    return MarketPressureRead(
        has_read=True,
        subject_side=subject_side,
        public_side=public_side,
        sharp_side=sharp_side,
        reverse_line_movement=rlm,
        steam_direction=steam.direction if steam.is_steam else 0,
        steam_originator=steam.originator if steam.is_steam else None,
        soft_book=dispersion.outlier_book if dispersion.is_soft_outlier else None,
        soft_offset=dispersion.outlier_offset if dispersion.is_soft_outlier else None,
        public_gap=public_gap,
        trap_flag=trap_flag,
        dog_value_flag=dog_value_flag,
        prob_adjustment=adjustment,
        confidence=confidence,
        rationale=rationale,
    )
