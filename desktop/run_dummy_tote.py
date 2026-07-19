#!/usr/bin/env python
"""Launch the Dummy Tote native desktop app.

Run with the desktop venv's interpreter (it carries PySide6/pyqtgraph):
    C:\\Users\\chris\\.dummy-desktop\\venv\\Scripts\\pythonw.exe desktop\\run_dummy_tote.py

The repo root (for the runtime artifacts) defaults to this checkout; override
with DUMMY_TOTE_ROOT or a positional arg.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # the dummy checkout
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from desktop.dummy_tote.app import run

    data_root = (sys.argv[1] if len(sys.argv) > 1
                 else os.environ.get("DUMMY_TOTE_ROOT") or str(ROOT))
    return run(data_root)


if __name__ == "__main__":
    raise SystemExit(main())
