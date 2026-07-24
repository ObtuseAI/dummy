"""Path constant for the frozen React archive tree.

This is NOT a serving adapter and never was. ``dashboard/frontend`` holds 295
archived per-version dashboards kept as governance evidence; since Wave-85 it
has no build tooling, and nothing imports, bundles, or serves it. The live
operator dashboard is Python (``autonomy/dashboard_ui.py``, served by the
``DummyDashboard`` task on :8787).

The previous docstring claimed the tree "is served independently (e.g., via
Vite in development or a static file server in production)". That was not true
of this system. See dashboard/frontend/README.md.
"""

from pathlib import Path

FRONTEND_PATH = Path(__file__).parent.parent / "dashboard" / "frontend"

__all__ = ["FRONTEND_PATH"]
