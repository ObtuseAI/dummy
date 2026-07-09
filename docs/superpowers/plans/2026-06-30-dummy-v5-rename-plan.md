# Dummy V5 Canonical Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Canonically rename the Dummy project to Dummy, preserve V4 behavior and historical artifacts, and produce all required V5 reports with full test validation.

**Architecture:** Filesystem rename of the repo root, bulk string replacement across source/dashboard/config/docs (excluding historical `artifacts/dummy/`), addition of minimal compatibility aliases, a new V5 report generator, and new regression tests.

**Tech Stack:** Python 3.11+, FastAPI, Vite/React, pytest, setuptools, git on Windows via Git Bash.

## Global Constraints

- Do not rebuild from scratch.
- Do not modify canonical Blunder (`C:/src/engine/obtuse/blunder`).
- Do not weaken the Live Broker Firewall.
- Do not add a paper-trading ladder.
- Do not expand the repo list.
- Do not place real live orders unless `configs/live_submit.json` has `enabled: true` with the required acknowledgement string.
- Do not claim PASS unless rename, separation, tests, dashboard build, and credential-aware Kalshi path are proven.
- Historical `artifacts/dummy/` records must not be edited.

---

## File mapping

| File | Responsibility |
|------|----------------|
| `scripts/rename_dumby_to_dummy.py` | One-off bulk string replacement across the new Dummy source tree |
| `core/state.py` | `DummyState` + `DummyState` compatibility alias |
| `adapters/base.py` | `DummyAdapter` + `DummyAdapter` compatibility alias |
| `core/ontology.py` | `dummy_probability` field |
| `pyproject.toml` | Project name `dummy`, module find list |
| `.env.example` | `DUMMY_*` env vars with backward fallback notes |
| `.gitignore` | `dummy.db`, `dummy.egg-info/`, `artifacts/dummy/`, keep `artifacts/dummy/` |
| `dashboard/frontend/index.html` | `<title>Dummy Dashboard</title>` |
| `dashboard/frontend/package.json` | `name: "dummy-dashboard"` |
| `dashboard/frontend/src/screens/*.jsx` | Labels renamed to Dummy |
| `dashboard/backend/v5_routes.py` | New V5 API routes (identity, migration, credential readiness, etc.) |
| `dashboard/backend/main.py` | Mounts `/api/v5` routes, keeps `/api/v4` for compatibility |
| `scripts/generate_v5_reports.py` | Generates all V5 reports under `artifacts/dummy/` |
| `scripts/compat_dumby_artifact_reader.py` | Reads old `artifacts/dummy/*.json` files |
| `tests/test_dummy_canonical_rename.py` | Verifies no `Dummy` strings remain in active source and identifiers are `Dummy` |
| `tests/test_dummy_blunder_separation.py` | Verifies Blinder untouched and Dummy does not import/write to it |
| `tests/test_dummy_path_migration.py` | Verifies migration manifest and old paths mapped |
| `tests/test_kalshi_credential_readiness.py` | Detects credentials without leaking values |
| `tests/test_real_kalshi_read_only_v2.py` | READ_ONLY ingestion v2 |
| `tests/test_no_order_in_read_only_v2.py` | No order-creating endpoints in READ_ONLY |
| `tests/test_kalshi_normalization_v2.py` | Normalization v2 |
| `tests/test_real_market_strategy_scan_v2.py` | Strategy scan v2 |
| `tests/test_live_cap_firewall_rehearsal_v2.py` | Firewall rehearsal v2 |
| `tests/test_no_secret_leak_v4.py` | Secret redaction v4 |
| `tests/test_dashboard_v5.py` | Dashboard V5 build and routes |
| `tests/test_live_submit_flag_guard.py` | Live submit gate |
| `tests/test_direct_order_bypass_v5.py` | Only firewall/submitter call create_order |

---

### Task 1: Safety snapshot of Blunder and Dummy git state

**Files:**
- Create: `proof/blunder_pre_rename_fingerprints.json`

**Interfaces:**
- Produces: SHA-256 fingerprints for every file under `C:/src/engine/obtuse/blunder`.

- [ ] **Step 1: Record pre-rename Blunder fingerprints**

Run from `C:/src/engine/dummy`:

```bash
python - <<'PY'
import json, hashlib, os
from pathlib import Path
root = Path("C:/src/engine/obtuse/blunder")
hashes = {}
for p in sorted(root.rglob("*")):
    if p.is_file():
        hashes[str(p.relative_to(root)).replace("\\", "/")] = hashlib.sha256(p.read_bytes()).hexdigest()
Path("proof/blunder_pre_rename_fingerprints.json").write_text(json.dumps({"root": str(root), "fingerprints": hashes}, indent=2))
print("recorded", len(hashes), "files")
PY
```

Expected output: `recorded N files`.

- [ ] **Step 2: Verify Dummy git has no uncommitted blockers**

Run:

```bash
git status --short
```

Expected: shows existing V4 modifications (acceptable). If there are uncommitted secrets, stop and redact them first.

---

### Task 2: Filesystem rename of the project root

**Files:**
- Move: `C:/src/engine/dummy` → `C:/src/engine/dummy`

**Interfaces:**
- Produces: `C:/src/engine/dummy` is the active root; `C:/src/engine/dummy` is absent.

- [ ] **Step 1: Move the directory**

```bash
mv /c/src/engine/dumby /c/src/engine/dummy
```

- [ ] **Step 2: Confirm `.git` moved and old root is gone**

```bash
ls -la /c/src/engine/dummy/.git/HEAD && test ! -d /c/src/engine/dumby && echo "rename ok"
```

Expected: `rename ok`.

- [ ] **Step 3: Create new artifact output directory**

```bash
mkdir -p /c/src/engine/dummy/artifacts/dummy
```

---

### Task 3: Bulk source-string replacement

**Files:**
- Create: `scripts/rename_dumby_to_dummy.py`

**Interfaces:**
- Consumes: source tree at `C:/src/engine/dummy`.
- Produces: modified source files with `Dummy` identifiers and paths.

- [ ] **Step 1: Write the rename script**

```python
# scripts/rename_dumby_to_dummy.py
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "artifacts", "dummy.egg-info", "dummy.egg-info", "logs",
}
SKIP_FILES = {"dummy.db", "dummy.db", ".env", "package-lock.json"}
TEXT_EXTS = {
    ".py", ".toml", ".md", ".txt", ".json", ".yml", ".yaml",
    ".html", ".jsx", ".js", ".css", ".cfg", ".ini",
}

REPLACEMENTS = [
    ("C:/src/engine/dummy", "C:/src/engine/dummy"),
    ("DummyState", "DummyState"),
    ("DummyAdapter", "DummyAdapter"),
    ("dummy_probability", "dummy_probability"),
    ("dummy-dashboard", "dummy-dashboard"),
    ("Dummy Dashboard", "Dummy Dashboard"),
    ("Dummy live trading", "Dummy live trading"),
    ("Dummy-native", "Dummy-native"),
    ("DUMMY_MODE", "DUMMY_MODE"),
    ("DUMMY_LOG_LEVEL", "DUMMY_LOG_LEVEL"),
    ("dummy.jsonl", "dummy.jsonl"),
    ("dummy.db", "dummy.db"),
    ("dummy.egg-info", "dummy.egg-info"),
    ("artifacts/dummy", "artifacts/dummy"),  # only affects new output paths
]


def should_process(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    for part in rel.parts[:-1]:
        if part in SKIP_DIRS:
            return False
    if path.name in SKIP_FILES:
        return False
    if path.suffix.lower() not in TEXT_EXTS:
        return False
    # Never modify historical V4 artifacts.
    if "artifacts/dummy" in str(rel).replace("\\", "/"):
        return False
    return True


def main() -> None:
    changed = 0
    for path in ROOT.rglob("*"):
        if not path.is_file() or not should_process(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        new_text = text
        for old, new in REPLACEMENTS:
            new_text = new_text.replace(old, new)
        # General UI / doc label replacement, but not inside historical artifacts.
        new_text = new_text.replace("Dummy", "Dummy")
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            changed += 1
            print("changed", path.relative_to(ROOT))
    print(f"done: {changed} files changed")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the rename script**

```bash
cd /c/src/engine/dummy
python scripts/rename_dumby_to_dummy.py
```

Expected: list of changed files, no errors.

- [ ] **Step 3: Manually verify high-risk files**

Check `pyproject.toml`, `core/state.py`, `adapters/base.py`, `dashboard/frontend/index.html`, `dashboard/frontend/package.json`, and a sample JSX file. Fix any over-replacement (e.g., a URL or external reference that legitimately contained `Dummy`).

---

### Task 4: Add compatibility aliases and env fallbacks

**Files:**
- Modify: `core/state.py`
- Modify: `adapters/base.py`
- Modify: any file reading `DUMMY_MODE` / `DUMMY_LOG_LEVEL` to also read `DUMBY_*`

**Interfaces:**
- Produces: `DummyState = DummyState`, `DummyAdapter = DummyAdapter`.

- [ ] **Step 1: Add aliases in `core/state.py`**

After `STATE = DummyState()`, append:

```python
DummyState = DummyState
```

- [ ] **Step 2: Add alias in `adapters/base.py`**

After `class DummyAdapter(ABC): ...`, append:

```python
DummyAdapter = DummyAdapter
```

- [ ] **Step 3: Add env fallback helper**

Create `core/env_compat.py`:

```python
import os

def get_env(name: str, legacy: str | None = None, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None and legacy:
        value = os.environ.get(legacy)
    return value if value is not None else default
```

Replace direct reads of `DUMMY_MODE` and `DUMMY_LOG_LEVEL` with `get_env("DUMMY_MODE", "DUMMY_MODE", ...)`. Use grep to find them.

---

### Task 5: Update build metadata and ignores

**Files:**
- Modify: `pyproject.toml`
- Modify: `.gitignore`

**Interfaces:**
- Produces: installable package named `dummy`.

- [ ] **Step 1: Update `pyproject.toml`**

```toml
[project]
name = "dummy"
```

Leave the module find list unchanged (top-level modules like `core`, `kalshi`, etc.).

- [ ] **Step 2: Update `.gitignore`**

Replace:

```gitignore
dummy.db
artifacts/dummy/
```

with:

```gitignore
dummy.db
dummy.db
artifacts/dummy/
artifacts/dummy/
```

Also add `dummy.egg-info/` if not present.

- [ ] **Step 3: Remove stale `dummy.egg-info/`**

```bash
rm -rf /c/src/engine/dummy/dummy.egg-info
```

Run `pip install -e .` if the project needs an editable install for tests; otherwise leave it.

---

### Task 6: Dashboard V5 update

**Files:**
- Modify: `dashboard/frontend/index.html`
- Modify: `dashboard/frontend/package.json`
- Modify: `dashboard/frontend/src/screens/Forecasts.jsx`, `Strategies.jsx`, `StrategyCandidates.jsx`
- Create: `dashboard/backend/v5_routes.py`
- Modify: `dashboard/backend/main.py`

**Interfaces:**
- Produces: `/api/v5/*` endpoints; frontend title and labels say Dummy.

- [ ] **Step 1: Update frontend labels**

Use the rename script output; verify `index.html`, `package.json`, and JSX screens.

- [ ] **Step 2: Create `dashboard/backend/v5_routes.py`**

Copy `dashboard/backend/v4_routes.py` to `v5_routes.py`. Rename route prefix functions and add endpoints:

```python
from fastapi import APIRouter
from pathlib import Path
import json

router = APIRouter(prefix="/v5")

ROOT = Path(__file__).parent.parent.parent
ARTIFACTS = ROOT / "artifacts" / "dummy"

@router.get("/identity")
def identity():
    return {
        "project": "Dummy",
        "root": str(ROOT),
        "milestone": "DUMMY_V5_CANONICAL_RENAME_REAL_KALSHI_READ_ONLY_AND_LIVE_CAP_REHEARSAL_V1",
        "previous_name": "Dummy",
    }

@router.get("/reports/{name}")
def report(name: str):
    path = ARTIFACTS / f"{name}.json"
    if not path.exists():
        return {"error": "not found"}
    return json.loads(path.read_text())
```

Add additional V5 endpoints mirroring v4 endpoints but reading from `artifacts/dummy/`.

- [ ] **Step 3: Mount V5 router in `dashboard/backend/main.py`**

```python
from dashboard.backend import v5_routes
app.include_router(v5_routes.router, prefix="/api")
```

Keep the v4 router mounted for historical compatibility.

---

### Task 7: V5 report generator

**Files:**
- Create: `scripts/generate_v5_reports.py`
- Create: `scripts/compat_dumby_artifact_reader.py`

**Interfaces:**
- Consumes: V4 report functions, Kalshi live data, strategy scanner, firewall.
- Produces: all required V5 JSON reports under `artifacts/dummy/`.

- [ ] **Step 1: Create compatibility reader**

```python
# scripts/compat_dumby_artifact_reader.py
from pathlib import Path
import json

OLD_ARTIFACTS = Path(__file__).parent.parent / "artifacts" / "dumby"

def read_v4(name: str) -> dict | None:
    path = OLD_ARTIFACTS / f"{name}.json"
    if path.exists():
        return json.loads(path.read_text())
    return None
```

- [ ] **Step 2: Create `scripts/generate_v5_reports.py`**

Start from a copy of `scripts/generate_v4_reports.py`.

Changes:

```python
ROOT = Path(__file__).parent.parent
ARTIFACTS = ROOT / "artifacts" / "dummy"
MILESTONE = "DUMMY_V5_CANONICAL_RENAME_REAL_KALSHI_READ_ONLY_AND_LIVE_CAP_REHEARSAL_V1"
```

Rename report functions to `_v2` where required and add new ones:

```python
def generate_dumby_to_dummy_rename_report() -> dict:
    return {
        "generated_at": now_iso(),
        "workstream": "V5: Canonical Dummy→Dummy rename",
        "old_root": "C:/src/engine/dummy",
        "new_root": str(ROOT),
        "old_root_absent": not Path("C:/src/engine/dummy").exists(),
        "new_root_present": ROOT.exists(),
        "verdict": "PASS" if (not Path("C:/src/engine/dummy").exists() and ROOT.exists()) else "FAIL",
    }

def generate_path_migration_manifest() -> dict:
    return {
        "generated_at": now_iso(),
        "mappings": [
            {"old": "C:/src/engine/dummy", "new": str(ROOT), "kind": "root"},
            {"old": "artifacts/dummy/", "new": "artifacts/dummy/", "kind": "report_output"},
            {"old": "dummy.db", "new": "dummy.db", "kind": "database"},
            {"old": "logs/dummy.jsonl", "new": "logs/dummy.jsonl", "kind": "log"},
            {"old": "DummyState", "new": "DummyState", "kind": "class"},
            {"old": "DummyAdapter", "new": "DummyAdapter", "kind": "class"},
            {"old": "dummy_probability", "new": "dummy_probability", "kind": "field"},
        ],
    }

def generate_dummy_canonical_identity_report() -> dict:
    return {
        "generated_at": now_iso(),
        "project": "Dummy",
        "milestone": MILESTONE,
        "previous_name": "Dummy",
        "compatibility_aliases": ["DummyState = DummyState", "DummyAdapter = DummyAdapter"],
        "historical_artifact_path": str(ROOT / "artifacts" / "dumby"),
    }
```

Add similar generators for Blunder recheck v3, independence report, credential readiness, strategy candidate quality, autonomous live capped path v2, firewall rehearsal regression v2, and dashboard v5.

At the bottom of the script, call all generators and write JSON files.

- [ ] **Step 3: Run the generator once to create reports**

```bash
cd /c/src/engine/dummy
python scripts/generate_v5_reports.py
```

Expected: all `artifacts/dummy/*.json` files created.

---

### Task 8: Required V5 regression tests

**Files:**
- Create: the 13 test files listed in the file mapping.

**Interfaces:**
- Each test asserts one safety or behavior requirement.

- [ ] **Step 1: Write `tests/test_dummy_canonical_rename.py`**

```python
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent

def test_active_root_is_dummy():
    assert ROOT.name == "dummy"
    assert not Path("C:/src/engine/dummy").exists()

def test_no_dumby_in_active_source():
    source_dirs = ["core", "kalshi", "live_firewall", "execution", "dashboard/backend", "strategies", "forecasting", "adapters"]
    for d in source_dirs:
        for p in (ROOT / d).rglob("*"):
            if p.is_file() and p.suffix in {".py", ".toml", ".md"}:
                text = p.read_text(encoding="utf-8")
                assert "Dummy" not in text, f"{p} still contains Dummy"

def test_dummy_identifiers_exist():
    from core.state import DummyState
    from adapters.base import DummyAdapter
    assert DummyState.__name__ == "DummyState"
    assert DummyAdapter.__name__ == "DummyAdapter"
```

- [ ] **Step 2: Write `tests/test_dummy_path_migration.py`**

```python
from pathlib import Path
import json

ROOT = Path(__file__).parent.parent

def test_migration_manifest_exists():
    path = ROOT / "artifacts" / "dummy" / "path_migration_manifest_v1.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert any(m["old"] == "C:/src/engine/dummy" and m["new"] == str(ROOT) for m in data["mappings"])
```

- [ ] **Step 3: Write remaining tests**

For each remaining test file, copy the V4 equivalent (e.g., `test_real_kalshi_read_only.py` → `test_real_kalshi_read_only_v2.py`) and update:

- Report path to `artifacts/dummy/*_v2.json`.
- Any `Dummy` references to `Dummy`.
- Add `test_live_submit_flag_guard.py` checking `configs/live_submit.json` defaults to disabled.
- Add `test_direct_order_bypass_v5.py` scanning for `create_order` calls outside `live_firewall/firewall.py` and `kalshi/submitter.py`.

---

### Task 9: Full validation

**Files:**
- Produces: `artifacts/dummy/tests_summary.json`, `artifacts/dummy/final_report.json`

- [ ] **Step 1: Run pytest**

```bash
cd /c/src/engine/dummy
python -m pytest tests/ -q --tb=short > artifacts/dummy/pytest_output.txt
```

Expected: all tests pass (or live tests skip if credentials absent).

- [ ] **Step 2: Build dashboard**

```bash
cd /c/src/engine/dummy/dashboard/frontend
npm ci
npm run build
```

Expected: `dist/` created without errors.

- [ ] **Step 3: Verify Blunder untouched after rename**

Run the fingerprint script again (now writing to `artifacts/dummy/blunder_separation_recheck_v3.json` with `post` fingerprints) and compare to `proof/blunder_pre_rename_fingerprints.json`.

- [ ] **Step 4: Generate final V5 reports**

```bash
cd /c/src/engine/dummy
python scripts/generate_v5_reports.py
```

- [ ] **Step 5: Inspect final report**

```bash
cat artifacts/dummy/final_report.json
```

Expected: verdict `PASS` or `PARTIAL`.

---

## Self-review checklist

- [ ] Every spec requirement maps to a task above.
- [ ] No placeholder text remains in the plan.
- [ ] `Dummy` historical artifacts are excluded from the bulk rename script.
- [ ] Live-submit gate is not weakened.
- [ ] Blunder fingerprints are recorded before and after.
