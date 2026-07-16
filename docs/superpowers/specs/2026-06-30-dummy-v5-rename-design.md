# Dummy V5 Canonical Rename Design

**Milestone:** `DUMMY_V5_CANONICAL_RENAME_REAL_KALSHI_READ_ONLY_AND_LIVE_CAP_REHEARSAL_V1`
**Date:** 2026-06-30
**Status:** Design approved (auto-permission mode)

## Goal

Canonically rename the project from **Dummy** to **Dummy** while preserving all V4 runtime behavior, Blunder separation, live-cap firewall gating, and secret redaction.

## Constraints

- Do not rebuild from scratch.
- Do not modify canonical Blunder (`C:/src/engine/obtuse/blunder`).
- Do not weaken the Live Broker Firewall.
- Do not add a paper-trading ladder.
- Do not expand the repo list.
- Do not place real live orders unless `configs/live_submit.json` has explicit operator approval.
- Do not claim PASS unless rename, separation, tests, dashboard build, and credential-aware Kalshi path are proven.

## Approach

**Approach A: filesystem rename + systematic string replacement with compatibility aliases.**

1. Record canonical Blunder fingerprints before any changes.
2. Move `C:/src/engine/dummy` → `C:/src/engine/dummy` (preserves `.git` history).
3. Replace canonical Dummy identifiers, paths, env vars, and labels with Dummy equivalents.
4. Keep backward-compatibility aliases only where needed to read older Dummy artifacts.
5. Preserve `artifacts/dummy/` historical records inside the new root.
6. Generate new reports under `artifacts/dummy/`.
7. Re-validate everything and recheck Blunder fingerprints.

## Rename surface

### Paths and filenames

| Old | New |
|-----|-----|
| `C:/src/engine/dummy` | `C:/src/engine/dummy` |
| `artifacts/dummy/` (new output) | `artifacts/dummy/` |
| `dummy.db` | `dummy.db` |
| `logs/dummy.jsonl` | `logs/dummy.jsonl` |
| `dummy.egg-info/` | `dummy.egg-info/` |

Historical V4 artifacts remain in `artifacts/dummy/` as read-only compatibility records.

### Python identifiers

| Old | New | Compatibility alias |
|-----|-----|---------------------|
| `DummyState` | `DummyState` | `DummyState = DummyState` (optional) |
| `DummyAdapter` | `DummyAdapter` | `DummyAdapter = DummyAdapter` (optional) |
| `dummy_probability` | `dummy_probability` | no alias needed |
| `DUMBY_*` env vars | `DUMMY_*` env vars | fallback read of `DUMBY_*` |

### Frontend

- `index.html` title: `Dummy Dashboard`
- `package.json` name: `dummy-dashboard`
- JSX labels: `Dummy` instead of `Dummy`

### Reports / milestone naming

- Milestone string: `DUMMY_V5_CANONICAL_RENAME_REAL_KALSHI_READ_ONLY_AND_LIVE_CAP_REHEARSAL_V1`
- Report generator: `scripts/generate_v5_reports.py`
- Report output root: `artifacts/dummy/`

## V5 feature work

### 1. Canonical rename

- Move/copy root.
- Replace strings.
- Add migration manifest.
- Add identity report.

### 2. Blunder separation recheck

- Record pre-rename Blunder fingerprints.
- Verify Dummy does not import from live Blunder absolute paths.
- Verify Dummy writes only to its own `configs/`, `logs/`, `artifacts/`, `proof/`, `dashboard/`.
- Record post-rename fingerprints.

### 3. Credential readiness audit

- Detect `KALSHI_API_KEY_ID` and `KALSHI_API_PRIVATE_KEY_PEM` / `KALSHI_API_PRIVATE_KEY_PATH`.
- Never log or write secret values; redact everywhere.
- If absent, skip live calls and mark reports `MOCK_ONLY` / `SKIP`.

### 4. Real Kalshi READ_ONLY ingestion

- Same V4 behavior; paths/labels updated.
- Track endpoints; block order-creating endpoints.
- Normalize data; reject stale/malformed data.

### 5. Real market strategy scan

- Run 8 strategy families against real data if credentials present; otherwise use V4 demo snapshot and mark `MOCK_ONLY`.
- Output `TradeProposal` or no-trade explanation.

### 6. AUTONOMOUS_LIVE_CAPPED firewall rehearsal

- Full capped path stops before submit.
- Real submit only when `configs/live_submit.json` is explicitly enabled with required acknowledgement string.

### 7. Dashboard V5

- Renamed labels.
- Screens: canonical identity, Blunder separation, credential readiness, real Kalshi connection, account balance (redacted), markets/orderbooks/positions/resting orders/fills, strategy proposals, firewall rehearsal verdicts, caps, live-submit flag, proof links.

### 8. Regression validation

- Full pytest, dashboard build, backend endpoint tests, rename regression tests, Blunder separation tests, no-secret-leak tests, no-order-in-read-only tests, direct-order-bypass tests, firewall rehearsal tests.

## Required new tests

- `test_dummy_canonical_rename.py`
- `test_dummy_blunder_separation.py`
- `test_dummy_path_migration.py`
- `test_kalshi_credential_readiness.py`
- `test_real_kalshi_read_only_v2.py`
- `test_no_order_in_read_only_v2.py`
- `test_kalshi_normalization_v2.py`
- `test_real_market_strategy_scan_v2.py`
- `test_live_cap_firewall_rehearsal_v2.py`
- `test_no_secret_leak_v4.py`
- `test_dashboard_v5.py`
- `test_live_submit_flag_guard.py`
- `test_direct_order_bypass_v5.py`

## Required reports

- `artifacts/dummy/final_report.json`
- `artifacts/dummy/tests_summary.json`
- `artifacts/dummy/dumby_to_dummy_rename_report_v1.json`
- `artifacts/dummy/path_migration_manifest_v1.json`
- `artifacts/dummy/dummy_canonical_identity_report_v1.json`
- `artifacts/dummy/blunder_separation_recheck_v3.json`
- `artifacts/dummy/dummy_independence_report_v1.json`
- `artifacts/dummy/kalshi_credential_readiness_report_v1.json`
- `artifacts/dummy/real_kalshi_read_only_report_v2.json`
- `artifacts/dummy/no_order_in_read_only_report_v2.json`
- `artifacts/dummy/kalshi_normalization_report_v2.json`
- `artifacts/dummy/real_market_strategy_scan_report_v2.json`
- `artifacts/dummy/strategy_candidate_quality_report_v1.json`
- `artifacts/dummy/live_cap_firewall_rehearsal_report_v2.json`
- `artifacts/dummy/autonomous_live_capped_path_report_v2.json`
- `artifacts/dummy/firewall_rehearsal_regression_report_v2.json`
- `artifacts/dummy/no_secret_leak_report_v4.json`
- `artifacts/dummy/dashboard_v5_report_v1.json`

## Pass / Partial / Fail criteria

- **PASS**: rename complete, Dummy root active, Blunder untouched, tests pass, dashboard builds, no secret leaks, no order endpoints in READ_ONLY, firewalls pass, all reports generated, real Kalshi READ_ONLY succeeds if credentials present.
- **PARTIAL**: rename complete, tests/dashboard/firewalls OK, but Kalshi credentials absent so live ingestion skipped.
- **FAIL**: Blunder modified, runtime broken, tests/dashboard fail, secrets leak, READ_ONLY calls order endpoints, direct order bypass exists, or live submit without explicit approval.
