# dashboard/frontend — frozen archive evidence, NOT a buildable app

This tree is **source evidence only**. There is deliberately no `package.json`,
no lockfile, and no build config. Do not add them back.

## What this is

`src/` holds 295 archived per-version dashboards (`V10Dashboard.jsx` …
`V130+Dashboard.jsx`) plus the operator screens they mount. It is the React
counterpart to the `predator_mesh/v*` snapshot tree, and it is load-bearing for
governance, not for serving traffic:

- `tests/test_vnext_final_audit.py::test_all_archived_dashboard_routes_are_lazy_and_preserved`
  pins that all 295 versions exist and are lazily routed from `App.jsx`.
- `scripts/run_vnext_final_audit.py` lists `src/VNextObservatory.jsx` as a
  required evidence path; the audit reports missing evidence if it disappears.
- `tests/test_dashboard_production_read_only.py` and
  `tests/test_vnext_phase7_observatory.py` pin the read-only truth contract —
  that these screens never fabricate a connection or performance claim.

## What serves the operator dashboard

Nothing here. The live operator dashboard is **Python**:
`autonomy/dashboard_ui.py`, served by the `DummyDashboard` scheduled task on
:8787. Nothing in this directory is imported, bundled, or served at runtime —
`adapters/react_dashboard.py` only ever exposed a path constant.

## Why the build tooling was removed (Wave-85, 2026-07-24)

All four open Dependabot alerts (`postcss`, `react-router` ×2,
`react-router-dom`) came from the npm manifest, not from the `.jsx` sources.
The build was already broken and unfixable without a forced resolution:
`@vitejs/plugin-react@4.7.0` declares peer `vite@^4||^5||^6||^7` while the
project declared and installed `vite@8.1.4`, so `npm install` failed on a
lockfile-only patch bump. `react-router` 6→7 is a breaking major, not a bump.

Deleting the manifest closes all four alerts permanently and removes a build
nothing ran, while keeping every governance assertion above intact. Deleting
`src/` instead would have destroyed the archive surface and broken the vNext
audit evidence chain.

If this ever needs to be a running app again, that is a new frontend decision —
start from the current Python dashboard's contract, not from this tree's
abandoned dependency graph.
