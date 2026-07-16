#!/usr/bin/env bash
# Verify a worktree's test suite is "clean" the way the improvement-wave program
# defines it, without any manual decomposition.
#
# WHY THIS EXISTS
#   Two things make a raw `pytest` count misleading in a dev worktree:
#     1. ~244 "workstation-only" governance tests (tests/workstation_only_tests.txt)
#        SKIP only when artifacts/dummy is absent; running the suite CREATES that
#        directory, so a second run in the same worktree "fails" them.
#     2. 13 canonical-path tests always fail off C:\src\engine\dummy.
#   CI mirrors the checkout to the canonical root and passes both sets. Locally,
#   the robust clean-signal is: every FAILED test is either workstation-only or
#   one of the 13 canonical-path tests. This script computes exactly that.
#
# USAGE
#   bash scripts/verify_wave_clean.sh [--cov] [PYTHON]
#     --cov     also run the CI coverage gate (--cov-fail-under=85) afterwards
#     PYTHON    python to use (default: .venv/Scripts/python.exe, then python)
#
# EXIT 0 = clean (only expected failures). EXIT 1 = real regressions (listed).
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 2

RUN_COV=0
PYBIN=""
for arg in "$@"; do
  case "$arg" in
    --cov) RUN_COV=1 ;;
    *) PYBIN="$arg" ;;
  esac
done
if [ -z "$PYBIN" ]; then
  if [ -x ".venv/Scripts/python.exe" ]; then PYBIN=".venv/Scripts/python.exe"
  elif [ -x ".venv/bin/python" ]; then PYBIN=".venv/bin/python"
  else PYBIN="python"; fi
fi

CANONICAL=$(cat <<'EOF'
test_dummy_canonical_identity_v2.py
test_dummy_canonical_identity_v3.py
test_dummy_canonical_identity_v4.py
test_dummy_canonical_identity_v9.py
test_dummy_canonical_identity_v10.py
test_dummy_canonical_identity_v11.py
test_dummy_canonical_identity_v12.py
test_dummy_canonical_identity_v13.py
test_dummy_canonical_identity_v14.py
test_dummy_canonical_identity_v16.py
test_dummy_canonical_rename.py
test_dummy_path_integrity.py
test_proof_ledger.py
EOF
)

LOG="$(mktemp)"
echo "[verify] running suite with $PYBIN ..."
"$PYBIN" -m pytest -q -o addopts="" -p no:cacheprovider > "$LOG" 2>&1
echo "[verify] $(grep -E '[0-9]+ (passed|failed)' "$LOG" | tail -1)"

EXPECTED="$(mktemp)"
{ printf '%s\n' "$CANONICAL"; tr -d '\r' < tests/workstation_only_tests.txt; } | sort -u > "$EXPECTED"

FAILED="$(mktemp)"
grep '^FAILED' "$LOG" | sed -E 's#^FAILED (tests/[^:]+).*#\1#' | xargs -n1 basename 2>/dev/null \
  | tr -d '\r' | sort -u > "$FAILED"

REGRESSIONS="$(comm -23 "$FAILED" "$EXPECTED")"
rc=0
if [ -n "$REGRESSIONS" ]; then
  echo "[verify] REAL REGRESSIONS (not workstation-only, not canonical-path):"
  echo "$REGRESSIONS" | sed 's/^/  - /'
  rc=1
else
  echo "[verify] CLEAN: every failure is workstation-only or one of the 13 canonical-path tests."
fi

if [ "$RUN_COV" = "1" ] && [ "$rc" = "0" ]; then
  echo "[verify] running CI coverage gate (13 canonical deselected, evidence hidden) ..."
  BK="$(mktemp -d)/artifacts_dummy"
  restore() { [ -d "$BK" ] && { rm -rf artifacts/dummy; mv "$BK" artifacts/dummy; }; }
  trap restore EXIT
  [ -d artifacts/dummy ] && mv artifacts/dummy "$BK"
  DESEL=()
  while read -r f; do [ -n "$f" ] && DESEL+=("--ignore=tests/$f"); done <<< "$CANONICAL"
  COVERAGE_FILE="$(mktemp)" "$PYBIN" -m pytest -q --timeout=120 -o addopts="" -p no:cacheprovider "${DESEL[@]}" \
    --cov=dummy --cov=core --cov=kalshi --cov=live_firewall --cov=compliance --cov=forecasting \
    --cov=strategies --cov=risk --cov=services --cov=adapters --cov=proof --cov=execution \
    --cov=model_router --cov=predator_mesh --cov=calibration --cov=autonomy \
    --cov-report=term --cov-fail-under=85 > "$LOG" 2>&1
  cov_rc=$?
  restore; trap - EXIT
  echo "[verify] $(grep -E '[0-9]+ (passed|failed)|Required test coverage' "$LOG" | tail -2)"
  [ "$cov_rc" != "0" ] && { echo "[verify] COVERAGE GATE FAILED"; rc=1; }
fi

echo "[verify] $([ "$rc" = "0" ] && echo CLEAN || echo DIRTY)"
exit "$rc"
