"""Run the read-only Dummy market observer over standard I/O."""
from autonomy.market_observer.server import run_stdio


if __name__ == "__main__":
    raise SystemExit(run_stdio())
