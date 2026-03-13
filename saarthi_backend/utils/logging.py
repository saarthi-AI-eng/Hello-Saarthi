"""Structured logging with optional request/conversation context."""

import logging
import sys
from typing import Any, Optional

# Default format
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a configured logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(level)
    return logger


def log_extra(request_id: Optional[str] = None, conversation_id: Optional[str] = None) -> dict[str, Any]:
    """Build extra dict for structured logging."""
    extra: dict[str, Any] = {}
    if request_id:
        extra["request_id"] = request_id
    if conversation_id:
        extra["conversation_id"] = conversation_id
    return extra
