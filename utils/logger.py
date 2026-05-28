"""Structured logging configuration using structlog."""

import logging
import os
import sys

import structlog

from config import settings


def _configure_structlog() -> None:
    """Configure structlog with appropriate renderer based on environment."""
    env = os.getenv("ENVIRONMENT", "development").lower()
    is_production = env == "production"

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if is_production:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging so structlog captures all logs
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)


# Run configuration on module import
_configure_structlog()


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger with the given name.

    Args:
        name: Logger name, typically __name__ of the calling module.

    Returns:
        A configured structlog BoundLogger instance.

    Example:
        from utils.logger import get_logger
        logger = get_logger(__name__)
        logger.info("server_started", port=8000)
    """
    return structlog.get_logger(name)
