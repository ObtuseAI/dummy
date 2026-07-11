# Archive: staged-gate governance era (V3–V304)

Historical one-shot report generators and their dashboard routers from the
2026-06/07 staged-gate governance pipeline. They are retired from active
development but remain importable and mounted so their reports, endpoints, and
tests keep working.

- `report_scripts/` — former `scripts/generate_v*_reports.py` and bundle
  runners. Imported by tests as `archive.report_scripts.generate_vNN_reports`.
- `routes/` — former `dashboard/backend/v*_routes.py`. Auto-mounted by
  `dashboard/backend/main.py` via a dynamic loop; each keeps its original
  `/api/vNN` prefix.

Command strings embedded in `predator_mesh/vNN/reports.py` (for example
`python scripts/generate_vNN_reports.py`) are frozen historical report text
and intentionally still reference the pre-archive paths; translate
`scripts/` → `archive/report_scripts/` and `dashboard/backend/vNN_routes.py`
→ `archive/routes/vNN_routes.py` if you ever need to re-run one.

Do not add new code here.
