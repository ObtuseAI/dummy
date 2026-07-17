#!/usr/bin/env bash
# Health-gated deploy of origin/main to the live checkout.
#
# The live box updates by hand today, which is how it silently drifted ~58
# commits behind main. This automates the safe path: fetch, checkout, sync
# deps, run ONE shadow cycle as a health gate, and roll back if that cycle
# fails -- so a bad deploy never leaves the daemon running broken code.
#
# Usage:  bash scripts/deploy_live.sh [PYTHON]
#   PYTHON  interpreter to use (default: C:/Python314/python.exe, then python)
#
# Shadow-only: never trades real money and never edits promotions.json.
set -u

cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 2

PYBIN="${1:-}"
if [ -z "$PYBIN" ]; then
  if [ -x "C:/Python314/python.exe" ]; then PYBIN="C:/Python314/python.exe"; else PYBIN="python"; fi
fi

ROLLBACK="$(git rev-parse --abbrev-ref HEAD)@$(git rev-parse --short HEAD)"
ROLLBACK_REF="$(git rev-parse HEAD)"
echo "[deploy] rollback point: $ROLLBACK"

if [ -n "$(git status --porcelain | grep -v '^??')" ]; then
  echo "[deploy] ABORT: uncommitted tracked changes present; commit or stash first." >&2
  exit 1
fi

echo "[deploy] fetching origin/main ..."
git fetch origin main --quiet || { echo "[deploy] ABORT: fetch failed" >&2; exit 1; }

echo "[deploy] checking out origin/main ..."
git checkout -B main origin/main || { echo "[deploy] ABORT: checkout failed" >&2; exit 1; }
echo "[deploy] now on main @ $(git rev-parse --short HEAD)"

echo "[deploy] syncing deps ..."
"$PYBIN" -m pip install -e . --quiet || { echo "[deploy] WARN: pip install returned nonzero"; }

echo "[deploy] health gate: import smoke ..."
if ! "$PYBIN" -c "import autonomy.session, autonomy.forecaster, autonomy.promotion, autonomy.reliability" 2>/dev/null; then
  echo "[deploy] HEALTH GATE FAILED (imports); rolling back to $ROLLBACK" >&2
  git checkout -B "$(echo "$ROLLBACK" | cut -d@ -f1)" "$ROLLBACK_REF"
  exit 1
fi

echo "[deploy] health gate: one shadow cycle ..."
if ! "$PYBIN" scripts/run_dummy_shadow_daemon.py; then
  echo "[deploy] HEALTH GATE FAILED (shadow cycle errored); rolling back to $ROLLBACK" >&2
  git checkout -B "$(echo "$ROLLBACK" | cut -d@ -f1)" "$ROLLBACK_REF"
  exit 1
fi

echo "[deploy] SUCCESS: live on main @ $(git rev-parse --short HEAD), shadow cycle clean."
echo "[deploy] (promotions.json is untouched -- capital promotion stays a manual operator step.)"
