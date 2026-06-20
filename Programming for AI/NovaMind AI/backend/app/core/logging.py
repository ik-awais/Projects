# backend/app/core/logging.py

"""
Centralized application logging.

Uses Python's standard library logging module exclusively — no third-party
logging frameworks. Provides a single configure_logging() entry point
(called once at app startup) and a get_logger() factory that every other
module should use instead of calling logging.getLogger() directly.
"""

import logging
import sys
from datetime import datetime, timezone

from app.core.config import settings

_LOG_RECORD_RESERVED_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName",
}


class StructuredFormatter(logging.Formatter):
    """
    Renders log records as single-line, key=value structured text — easy
    to grep locally and easy to parse if later piped into a log aggregator,
    without depending on an external structured-logging library.

    Example output:
    2026-06-19T12:00:00.123Z level=INFO logger=app.services.auth_service
    msg="User registered" user_id=... request_id=...
    """

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z")

        base = (
            f'{timestamp} level={record.levelname} logger={record.name} '
            f'msg="{record.getMessage()}"'
        )

        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _LOG_RECORD_RESERVED_ATTRS and not key.startswith("_")
        }
        if extras:
            extras_str = " ".join(f"{key}={value!r}" for key, value in sorted(extras.items()))
            base = f"{base} {extras_str}"

        if record.exc_info:
            base = f"{base}\n{self.formatException(record.exc_info)}"

        return base


def configure_logging() -> None:
    """
    Configures the root logger once at application startup. Subsequent
    calls are safe no-ops (handlers are not duplicated) so this can be
    called defensively from multiple entry points (main.py, worker
    processes, scripts) without producing duplicate log lines.
    """
    root_logger = logging.getLogger()

    if root_logger.handlers:
        return

    log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    root_logger.setLevel(log_level)

    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(console_handler)

    # Quiet noisy third-party loggers to WARNING regardless of app log
    # level, so DEBUG mode doesn't flood output with driver-level chatter.
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.DATABASE_ECHO else logging.WARNING
    )
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Returns a named logger. Use __name__ as the argument from any module:

        from app.core.logging import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened", extra={"user_id": str(user.id)})

    Does not call configure_logging() itself — that must happen exactly
    once at process startup (main.py's lifespan handler does this), so
    that handler configuration is centralized and predictable.
    """
    return logging.getLogger(name)