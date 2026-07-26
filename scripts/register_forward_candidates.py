"""Register forward-evidence candidate fingerprints for the edge scopes.

Registration is a *precondition*, never authority: `auto_promotion` only
counts witnessed-fill evidence that arrives strictly after an immutable
registration whose fingerprint matches the one stamped on the candidate's
own signals (`promotion_candidate_fingerprint`). Until a scope is registered
its forward clock simply never starts — which is why the historical edge
candidates had zero forward evidence. A registration whose scope no longer
matches what the source EMITS is equally inert: the scope must be the exact
`autonomy.taxonomy.grading_scope` of a real emission's features.

The fingerprint binds scope + the exact implementation bytes of the source's
signal module at registration time, so a later re-implementation cannot
silently inherit the old registration.

Idempotent: existing registrations are never modified or re-dated. Run:

    python scripts/register_forward_candidates.py           # writes/updates
    python scripts/register_forward_candidates.py --dry-run # show only
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.signals.market_debias import PROMOTION_ELIGIBLE_SCOPES
from autonomy.signals.crypto_equities import (
    PROMOTION_ELIGIBLE_SCOPE as EQUITIES_PROMOTION_ELIGIBLE_SCOPE,
)
from autonomy.signals.crypto_macro import (
    PROMOTION_ELIGIBLE_SCOPE as MACRO_PROMOTION_ELIGIBLE_SCOPE,
)

REGISTRATIONS_PATH = ROOT / "runtime" / "autonomy" / "promotion_forward_registrations.json"

MARKET_DEBIAS_MODULE = "autonomy/signals/market_debias.py"

# The historical edge candidates from the 2026-07-22 elite audit, mapped to the
# module that implements each source. Research candidates only; promotion still
# requires every auto_promotion stage-1 gate to pass forward.
#
# market_debias scopes are IMPORTED from the signal module rather than repeated
# here. The original literal ("market_debias|mlb|na|pre") went stale the moment
# emissions started stamping market_type as "<type>@<horizon>" (8c43272): the
# registered scope stopped matching any emission's grading_scope, so neither the
# ledger fingerprint stamp nor the challenger lane could ever start that
# candidate's forward clock. One source of truth removes that drift class.
CANDIDATES: tuple[tuple[str, str], ...] = (
    (EQUITIES_PROMOTION_ELIGIBLE_SCOPE, "autonomy/signals/crypto_equities.py"),
    (MACRO_PROMOTION_ELIGIBLE_SCOPE, "autonomy/signals/crypto_macro.py"),
) + tuple(
    (scope, MARKET_DEBIAS_MODULE) for scope in sorted(PROMOTION_ELIGIBLE_SCOPES)
)


def candidate_fingerprint(scope: str, module_path: Path) -> str:
    """SHA-256 binding the scope to the implementation bytes it names."""
    module_digest = hashlib.sha256(module_path.read_bytes()).hexdigest()
    return hashlib.sha256(f"{scope}:{module_digest}".encode("utf-8")).hexdigest()


def build_registrations(existing: dict) -> tuple[dict, list[dict]]:
    """Merge missing candidates into the registrations document."""
    entries = list(existing.get("registrations") or [])
    known = {
        str(entry.get("scope") or "")
        for entry in entries
        if isinstance(entry, dict)
    }
    added: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()
    for scope, rel_module in CANDIDATES:
        if scope in known:
            continue
        module_path = ROOT / rel_module
        entry = {
            "scope": scope,
            "candidate_fingerprint": candidate_fingerprint(scope, module_path),
            "registered_at": now,
            "definition_module": rel_module,
            "registered_by": "scripts/register_forward_candidates.py",
            "authority": "none_registration_is_a_precondition_not_a_promotion",
        }
        entries.append(entry)
        added.append(entry)
    return {"registrations": entries}, added


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--path", type=Path, default=REGISTRATIONS_PATH)
    args = parser.parse_args()

    existing: dict = {}
    if args.path.exists():
        try:
            existing = json.loads(args.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            print(json.dumps({"status": "ERROR_UNREADABLE_EXISTING", "path": str(args.path)}))
            return 1
        if not isinstance(existing, dict):
            existing = {}

    document, added = build_registrations(existing)
    report = {
        "status": "DRY_RUN" if args.dry_run else "OK",
        "path": str(args.path),
        "registered_total": len(document["registrations"]),
        "added_now": [entry["scope"] for entry in added],
        "authority": "none",
    }
    if not args.dry_run and added:
        args.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(args.path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(document, stream, indent=2, sort_keys=True)
            os.replace(tmp, args.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
