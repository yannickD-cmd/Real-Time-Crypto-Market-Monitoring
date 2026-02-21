"""Structured logging configuration."""
import os
import json
import logging
from typing import Any
import structlog


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Configure structured logging."""
    
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level),
    )

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if log_format == "json" else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a logger instance."""
    return structlog.get_logger(name)


class LogContext:
    """Context manager for structured logging with exception handling."""
    
    def __init__(self, logger: structlog.BoundLogger, operation: str, **context):
        self.logger = logger
        self.operation = operation
        self.context = context
    
    def __enter__(self) -> structlog.BoundLogger:
        self.logger = self.logger.bind(**self.context)
        self.logger.info("operation_started", operation=self.operation)
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.logger.exception(
                "operation_failed",
                operation=self.operation,
                exception=str(exc_val)
            )
            return False
        self.logger.info("operation_completed", operation=self.operation)
        return True
