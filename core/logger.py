import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from core.secret_guard import redact

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "dummy.jsonl"

# LogRecord attributes that are plumbing, not caller-supplied context. Anything
# a caller passes via ``extra=`` lands as an unknown attribute and is emitted.
# (The old five-field whitelist dropped every extra — 20k 'Kalshi API error'
# lines carried status/category that never reached disk; 2026-07-24 audit.)
_RESERVED_RECORD_ATTRS = frozenset(vars(
    logging.LogRecord("", 0, "", 0, "", (), None)
)) | {"message", "asctime", "taskName"}


class JsonlHandler(logging.Handler):
    def emit(self, record: logging.LogRecord):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "component": getattr(record, "component", "unknown"),
        }
        for key, value in vars(record).items():
            if key in _RESERVED_RECORD_ATTRS or key in payload:
                continue
            try:
                json.dumps(value, default=str)
            except (TypeError, ValueError):
                value = repr(value)
            payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        safe = redact(payload)
        with LOG_FILE.open("a") as f:
            f.write(json.dumps(safe, default=str) + "\n")

logger = logging.getLogger("dummy")
logger.setLevel(logging.INFO)
logger.addHandler(JsonlHandler())
