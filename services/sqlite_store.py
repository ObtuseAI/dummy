import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "dumby.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS status (
    id INTEGER PRIMARY KEY,
    mode TEXT,
    kill_switch_active BOOLEAN,
    emergency_stop_active BOOLEAN,
    kalshi_connected BOOLEAN,
    balance_cents INTEGER,
    daily_loss_cents INTEGER,
    total_exposure_cents INTEGER,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    market_ticker TEXT,
    contract_ticker TEXT,
    side TEXT,
    price_cents INTEGER,
    size INTEGER,
    status TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS positions (
    market_ticker TEXT PRIMARY KEY,
    contract_ticker TEXT,
    side TEXT,
    quantity INTEGER,
    avg_price_cents INTEGER,
    unrealized_pnl_cents INTEGER
);
CREATE TABLE IF NOT EXISTS repo_harvester (
    owner TEXT,
    name TEXT,
    verdict TEXT,
    fetched_at TEXT
);
"""

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()

async def get_orders():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM orders ORDER BY created_at DESC") as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def get_positions():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM positions") as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def insert_order(order_id: str, market_ticker: str, contract_ticker: str, side: str, price_cents: int, size: int, status: str = "open"):
    from datetime import datetime, timezone
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (order_id, market_ticker, contract_ticker, side, price_cents, size, status, datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()
