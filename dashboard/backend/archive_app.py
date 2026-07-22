"""Explicit historical dashboard surface for offline development only.

This module is intentionally separate from ``dashboard.backend.main``. The
production application never imports or mounts archived V3-V304 routers unless
``DUMMY_DASHBOARD_ARCHIVE_SURFACE=offline-dev`` is set before import. Run the
bundled launcher, which binds only to loopback, when historical report screens
are needed.

Archived routes are not an execution surface and are not supported for live or
credentialed operation. Keep provider and broker credentials out of the archive
process environment.
"""

from __future__ import annotations

import os

EXPECTED_MODE = "offline-dev"
ENV_VAR = "DUMMY_DASHBOARD_ARCHIVE_SURFACE"

if os.environ.get(ENV_VAR, "").strip().lower() != EXPECTED_MODE:
    raise RuntimeError(
        "archived dashboard routes are disabled; launch with "
        "scripts/run_dummy_archive_dashboard.py for the explicit offline-dev surface"
    )

from dashboard.backend.main import app  # noqa: E402,F401

if getattr(app.state, "dashboard_surface", None) != "offline_archive":
    raise RuntimeError("archive surface failed closed before historical routers were mounted")

