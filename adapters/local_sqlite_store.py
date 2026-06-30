"""Dashboard adapter: re-export the local SQLite persistence layer."""

from services.sqlite_store import init_db, get_orders, get_positions, insert_order

__all__ = ["init_db", "get_orders", "get_positions", "insert_order"]
