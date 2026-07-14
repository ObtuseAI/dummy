import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from core.secret_guard import redact

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "dummy.jsonl"

class JsonlHandler(logging.Handler):
    def emit(self, record: logging.LogRecord):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "component": getattr(record, "component", "unknown"),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        safe = redact(payload)
        with LOG_FILE.open("a") as f:
            f.write(json.dumps(safe, default=str) + "\n")

logger = logging.getLogger("dummy")
logger.setLevel(logging.INFO)
logger.addHandler(JsonlHandler())
