import logging
from typing import Literal

import structlog
from structlog.typing import FilteringBoundLogger


def configure_logging(log_format: Literal["console", "json"]) -> None:
    renderers = {
        "console": structlog.dev.ConsoleRenderer(),
        "json": structlog.processors.JSONRenderer(),
    }

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderers[log_format],
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> FilteringBoundLogger:
    return structlog.get_logger(name)
