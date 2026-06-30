"""Dashboard adapter: placeholder for the React frontend.

The frontend source lives at dashboard/frontend/ and is served independently
(e.g., via Vite in development or a static file server in production).
"""

from pathlib import Path

FRONTEND_PATH = Path(__file__).parent.parent / "dashboard" / "frontend"

__all__ = ["FRONTEND_PATH"]
