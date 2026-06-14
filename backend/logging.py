"""
Structured logging for HelioOps backend.

Uses structlog for JSON-formatted logs in production and
human-readable console logs in development.

Usage:
    from backend.logging import get_logger
    log = get_logger("backend.pipeline")
    log.info("pipeline_started", storm_id="2024-10-G4")
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone

import structlog


def _add_timestamp(logger, method_name, event_dict):
    event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
    return event_dict


def _add_service_name(logger, method_name, event_dict):
    event_dict.setdefault("service", "helioops-backend")
    return event_dict


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        _add_timestamp,
        _add_service_name,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)