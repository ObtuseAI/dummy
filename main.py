import os

import uvicorn
from dashboard.backend.main import app


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.environ.get("DUMMY_DASHBOARD_HOST", "127.0.0.1"),
        port=int(os.environ.get("DUMMY_DASHBOARD_PORT", "8000")),
        log_level="info",
    )
