"""Structured logging configuration using structlog.

Why structlog instead of stdlib logging?
- Structured output: logs as JSON in production (machine-parseable)
- Pretty console output: colored, readable logs in development
- Context binding: attach key-value pairs to log entries (request_id, user_id)
- Processors pipeline: transform log entries through a chain of processors
- Thread/async safe: works correctly with FastAPI's async architecture

In production, structured JSON logs integrate with log aggregation services
(DataDog, CloudWatch, ELK Stack) for searching and alerting.
"""

import logging
import sys

import structlog


def setup_logging(environment: str = "development", debug: bool = False) -> None:
    """Configure structured logging for the application.

    Args:
        environment: Current environment. "production" uses JSON output,
                     all other environments use colored console output.
        debug: If True, sets log level to DEBUG. Otherwise INFO.
    """
    log_level = logging.DEBUG if debug else logging.INFO

    # Shared processors used in both dev and prod
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,  # Merge context from contextvars
        structlog.stdlib.add_log_level,           # Add 'level' key
        structlog.stdlib.add_logger_name,         # Add 'logger' key
        structlog.processors.TimeStamper(fmt="iso"),  # ISO 8601 timestamps
        structlog.processors.StackInfoRenderer(),     # Stack info if requested
        structlog.processors.UnicodeDecoder(),        # Decode bytes to str
    ]

    if environment == "production":
        # JSON output for production — machine-parseable
        renderer = structlog.processors.JSONRenderer()
    else:
        # Colored console output for development — human-readable
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            pad_event=40,
        )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to use structlog's formatter
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Quiet noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if debug else logging.WARNING
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (typically __name__ of the calling module).

    Returns:
        A bound structlog logger with the given name.
    """
    return structlog.get_logger(name)
