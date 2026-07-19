"""Synthesis: turn movement + steam + dispersion + public-lean (+ scraped
splits) into one sharp/public read per game side.

Two independent tells, fused:

  * reverse line movement -- the public piles onto the predictable side, so a
    CONFIRMED line move to the OTHER side is heavier money overriding ticket
    volume (Wave-30, line-only);
  * money vs tickets -- when the share of MONEY on a side runs ahead of its
    share of BETS, fewer-but-bigger sharp bets are there (Wave-32, from
    scraped splits).

When both are present and agree, conviction rises; when they conflict, it is
penalised and the money channel (handle is the sharper signal) is preferred.
Scraped tickets also make the trap real: a heavy MEASURED public side the line
will not confirm -- flat OR against -- is books shading the public, the
flat-line trap the line-only tier could not safely call. Dog value: whenever
the sharp side is the underdog.

Pure function; the signal feeds it and turns ``prob_adjustment`` into a
capped, challenger-only nudge.
"""
from __future__ import annotations

from dataclasses import dataclass

from autonomy.market_pressure.dispersion import DispersionRead
from autonomy.market_pressure.public_lean import PublicLeanRead
from autonomy.market_pressure.splits.model import FusedSplits
from autonomy.market_pressure.steam import SteamRead

# A public gap this wide is a genuine public side (else the crowd is split and
# "fade the public" is meaningless).
TRAP_PUBLIC_GAP = 0.20
# Money% must lead ticket% by this much on a side to call it sharp.
MONEY_DIVERGENCE_THRESHOLD = 0.07
# Hard cap on the probability nudge -- a challenger hint, not a model.
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
    # Wave-32 splits channel (None when splits are absent).
    public_is_measured: bool = False
    subject_ticket_pct: float | None = None
    money_sharp_side: str | None = None
    signals_agree: bool | None = None
    splits_sources: tuple[str, ...] = ()

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
            "public_is_measured": self.public_is_measured,
            "subject_ticket_pct": (round(self.subject_ticket_pct, 4)
                                   if self.subject_ticket_pct is not None else None),
            "money_sharp_side": self.money_sharp_side,
            "signals_agree": self.signals_agree,
            "splits_sources": list(self.splits_sources),
        }


def _no_read(subject_side: str) -> MarketPressureRead:
    return MarketPressureRead(
        has_read=False, subject_side=subject_side, public_side=None, sharp_side=None,
        reverse_line_movement=False, steam_direction=0, steam_originator=None,
        soft_book=None, soft_offset=None, public_gap=0.0, trap_flag=False,
        dog_value_flag=False, prob_adjustment=0.0, confidence=0.0,
        rationale="no market-pressure read")


def _public_from_splits(
    splits: FusedSplits, subject_side: str, opponent_side: str, subject_is_home: bool,
) -> tuple[str | None, float, float, str | None, float | None]:
    """(public_side, public_gap, subject_ticket, money_sharp_side, subject_money_gap)
    from MEASURED tickets/money, subject-perspective."""
    subj_ticket = (splits.home_ticket_pct if subject_is_home else splits.away_ticket_pct)
    if subj_ticket is None:
        return None, 0.0, None, None, None  # type: ignore[return-value]
    opp_ticket = 1.0 - subj_ticket
    public_gap = abs(subj_ticket - opp_ticket)
    public_side = subject_side if subj_ticket >= opp_ticket else opponent_side

    subj_money_gap = None
    money_sharp = None
    if splits.home_money_ticket_gap is not None:
        subj_money_gap = (splits.home_money_ticket_gap if subject_is_home
                          else -splits.home_money_ticket_gap)
        if subj_money_gap >= MONEY_DIVERGENCE_THRESHOLD:
            money_sharp = subject_side
        elif subj_money_gap <= -MONEY_DIVERGENCE_THRESHOLD:
            money_sharp = opponent_side
    return public_side, public_gap, subj_ticket, money_sharp, subj_money_gap


def synthesize_pressure(
    *,
    subject_side: str,
    opponent_side: str,
    subject_devig: float | None,
    subject_lean: PublicLeanRead,
    opponent_lean: PublicLeanRead,
    steam: SteamRead,
    dispersion: DispersionRead,
    splits: FusedSplits | None = None,
    subject_is_home: bool = True,
) -> MarketPressureRead:
    """Combine the reads for ONE game (subject's perspective).

    ``steam.direction`` +1 means the subject's number moved up (money toward
    the subject), -1 toward the opponent. ``splits`` supersedes the estimated
    public lean when present. Fail-closed: with no steam, no public side, and
    no money signal there is nothing to say."""
    measured = bool(splits and splits.has_read and splits.home_ticket_pct is not None)
    subject_ticket = money_sharp = subject_money_gap = None
    splits_sources: tuple[str, ...] = ()

    if measured:
        (public_side, public_gap, subject_ticket, money_sharp,
         subject_money_gap) = _public_from_splits(
            splits, subject_side, opponent_side, subject_is_home)
        splits_sources = splits.sources
    else:
        public_gap = abs(subject_lean.lean - opponent_lean.lean)
        public_side = (subject_side if subject_lean.lean >= opponent_lean.lean
                       else opponent_side) if public_gap > 1e-6 else None

    # Which side did a CONFIRMED line move run to?
    line_toward: str | None = None
    if steam.is_steam and steam.direction != 0:
        line_toward = subject_side if steam.direction > 0 else opponent_side

    if line_toward is None and public_side is None and money_sharp is None:
        return _no_read(subject_side)

    rlm = bool(line_toward and public_side and line_toward != public_side
               and public_gap >= TRAP_PUBLIC_GAP)

    line_sharp: str | None = None
    if rlm:
        line_sharp = line_toward
    elif line_toward and (public_side is None or line_toward != public_side):
        line_sharp = line_toward

    # Fuse the two sharp tells.
    signals_agree: bool | None = None
    if money_sharp and line_sharp:
        signals_agree = money_sharp == line_sharp
        sharp_side = money_sharp                       # handle is the sharper channel
    elif money_sharp:
        sharp_side = money_sharp
    else:
        sharp_side = line_sharp

    # Trap. With MEASURED tickets a heavy public side the line will not confirm
    # (flat OR against) is a real trap; line-only, only a confirmed reverse move.
    if measured:
        trap_flag = bool(public_side is not None and public_gap >= TRAP_PUBLIC_GAP
                         and line_toward != public_side)
    else:
        trap_flag = rlm

    dog_value_flag = bool(
        sharp_side is not None and subject_devig is not None and (
            (sharp_side == subject_side and subject_devig < 0.5)
            or (sharp_side == opponent_side and subject_devig >= 0.5)))

    adjustment = 0.0
    confidence = 0.0
    if sharp_side is not None:
        strength = min(1.0, abs(steam.magnitude) / 0.03) if steam.is_steam else 0.4
        gap_weight = min(1.0, public_gap / 0.4) if rlm or measured else 0.5
        money_weight = (min(1.0, abs(subject_money_gap) / 0.15)
                        if subject_money_gap is not None else 0.0)
        confidence = 0.4 * strength + 0.3 * gap_weight + 0.3 * money_weight
        if signals_agree:
            confidence = min(1.0, confidence * 1.3)    # both tells agree
        elif signals_agree is False:
            confidence *= 0.6                          # tells conflict
        confidence = round(confidence, 3)
        magnitude = min(ADJ_CAP, ADJ_CAP * confidence)
        adjustment = magnitude if sharp_side == subject_side else -magnitude

    bits = []
    if public_side:
        tag = "public" if measured else "est. public"
        bits.append(f"{tag} on {public_side} ({'ticket ' if measured else ''}gap {public_gap:.2f})")
    if money_sharp:
        bits.append(f"money on {money_sharp}")
    if sharp_side:
        agree = " [confirmed]" if signals_agree else (" [conflict]" if signals_agree is False else "")
        bits.append(f"sharp on {sharp_side}" + (" [RLM]" if rlm else "") + agree)
    if trap_flag:
        bits.append(f"trap: fade {public_side}")
    if dog_value_flag:
        bits.append(f"dog value on {sharp_side}")
    if dispersion.is_soft_outlier and dispersion.outlier_book:
        bits.append(f"soft {dispersion.outlier_book}")
    rationale = "; ".join(bits) or "no actionable pressure"

    return MarketPressureRead(
        has_read=True, subject_side=subject_side, public_side=public_side,
        sharp_side=sharp_side, reverse_line_movement=rlm,
        steam_direction=steam.direction if steam.is_steam else 0,
        steam_originator=steam.originator if steam.is_steam else None,
        soft_book=dispersion.outlier_book if dispersion.is_soft_outlier else None,
        soft_offset=dispersion.outlier_offset if dispersion.is_soft_outlier else None,
        public_gap=public_gap, trap_flag=trap_flag, dog_value_flag=dog_value_flag,
        prob_adjustment=adjustment, confidence=confidence, rationale=rationale,
        public_is_measured=measured, subject_ticket_pct=subject_ticket,
        money_sharp_side=money_sharp, signals_agree=signals_agree,
        splits_sources=splits_sources)
