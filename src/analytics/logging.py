"""Small structured logging helper.

The project does not need a logging framework. A JSON formatter keeps local
and deployment logs machine-readable without adding a dependency.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Format one log record as a single JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key in ("dataset_version", "registry_version", "endpoint", "duration_ms"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str = "flame.analytics") -> logging.Logger:
    """Return a logger configured once with the JSON formatter."""

    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(os.environ.get("FLAME_LOG_LEVEL", "INFO").upper())
        logger.propagate = False
    return logger
