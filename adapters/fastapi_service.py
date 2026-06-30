"""Dashboard adapter: re-export the backend FastAPI application."""

from dashboard.backend.main import app

__all__ = ["app"]
