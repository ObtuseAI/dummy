# scripts/verify_statsapi_live.py
"""One-shot live check of the MLB StatsAPI parsers against a real slate.

Read-only, keyless. Prints how many of tonight's games populated each field
so a human can confirm the foundation works end-to-end before model heads
consume it. Not part of the hermetic test suite.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

from autonomy.sports.statsapi import StatsApiClient


def main() -> int:
    date_iso = sys.argv[1] if len(sys.argv) > 1 else datetime.now(timezone.utc).date().isoformat()
    now = datetime.now(timezone.utc).isoformat()
    client = StatsApiClient()
    contexts = client.projected_contexts(date_iso, captured_at=now)
    if not contexts:
        print(f"No MLB games found for {date_iso}")
        return 0
    fields_seen = {k: 0 for k in contexts[0].field_provenance()}
    for ctx in contexts:
        for field_name, present in ctx.field_provenance().items():
            fields_seen[field_name] += int(present)
    total = len(contexts)
    print(f"{date_iso}: {total} games")
    for field_name, count in sorted(fields_seen.items(), key=lambda kv: -kv[1]):
        print(f"  {field_name:28} {count}/{total}")
    # Prove a confirmed-lineup promotion works on the first game with a boxscore.
    sample = contexts[0]
    confirmed = client.confirm_lineups(sample, captured_at=now)
    print(
        f"confirm_lineups({sample.game_pk}): "
        f"home {len(confirmed.home_lineup)} / away {len(confirmed.away_lineup)} batters"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
