"""One-shot live-shape validation of the four splits providers.

The splits tier ships inert because each provider's live response shape was
best-effort. This runner performs exactly one polite fetch per provider for
one league, asserts the parse yields non-empty, sane reads, and writes a
validation artifact — the documented gate for arming DUMMY_SPLITS_ENABLED=1.

Read-only market intelligence: no order path, no ledger writes, no arming
side effects. Arming remains an explicit env decision after reviewing the
artifact.

    python scripts/run_splits_shape_validation.py --league mlb
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.market_pressure.splits.fetch import PoliteFetcher  # noqa: E402
from autonomy.market_pressure.splits.providers import default_providers  # noqa: E402

ARTIFACT_PATH = Path("runtime/autonomy/splits_shape_validation.json")


def _read_summary(read) -> dict:
    return {
        "home": read.home_team,
        "away": read.away_team,
        "has_ticket_pct": read.has_tickets(),
        "has_money_pct": read.has_money(),
    }


def validate_providers(league: str) -> dict:
    fetcher = PoliteFetcher()
    now = time.time()
    results = []
    for provider in default_providers():
        name = type(provider).__name__
        entry: dict = {"provider": name, "league": league}
        try:
            reads = provider.fetch(league, fetcher, now=now)
        except Exception as exc:  # noqa: BLE001 - shape validation must report, not crash
            entry.update({
                "status": "FETCH_ERROR",
                "error": f"{type(exc).__name__}: {exc}"[:160],
            })
            results.append(entry)
            continue
        valid = [
            r for r in reads
            if r.home_team and r.away_team and (r.has_tickets() or r.has_money())
        ]
        entry.update({
            "status": "OK" if valid else "EMPTY_PARSE",
            "reads": len(reads),
            "valid_reads": len(valid),
            "samples": [_read_summary(r) for r in valid[:3]],
        })
        results.append(entry)
    ok = [r for r in results if r["status"] == "OK"]
    return {
        "artifact_version": "splits_shape_validation_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "league": league,
        "providers": results,
        "providers_ok": [r["provider"] for r in ok],
        "verdict": (
            "ARM_ELIGIBLE" if len(ok) >= 2 else
            "PARTIAL" if ok else "NOT_VALIDATED"
        ),
        "arming_note": (
            "Arming is an explicit operator/env action (DUMMY_SPLITS_ENABLED=1)."
            " The tier is challenger-only, capped at 0.04, and fails open on"
            " fetch / closed on opinion regardless."
        ),
        "authority": {"execution": False, "fusion_weight_change": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--league", default="mlb")
    args = parser.parse_args()
    report = validate_providers(args.league)
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = ARTIFACT_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(ARTIFACT_PATH)
    print(json.dumps({
        "verdict": report["verdict"],
        "providers_ok": report["providers_ok"],
        "artifact": str(ARTIFACT_PATH),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
