"""
AgentX Logging Framework

Centralized logging configuration for the entire project.
Provides consistent formatting, file rotation, and easy-to-use interface.

Usage:
    from backend.utils.logger import get_logger
    logger = get_logger(__name__)

    logger.info("User action", user_id="123", action="login")
    logger.error("Operation failed", exc_info=True, operation="save")
"""

import logging
import logging.handlers
import sys
import os
import io
import json
from typing import Optional, Any, Dict
from datetime import datetime
from functools import lru_cache


# =============================================================================
# Log Level Constants
# =============================================================================

LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


# =============================================================================
# Custom Formatter with Context Support
# =============================================================================

class AgentXFormatter(logging.Formatter):
    """
    Custom formatter that supports:
    - Automatic file location detection
    - Structured context fields
    - Color output for console (optional)
    """

    # ANSI color codes for console output
    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",      # Reset
    }

    def __init__(self, fmt: str, datefmt: str = None, use_colors: bool = False):
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        # Add location info if not present
        if not hasattr(record, 'location') or not record.location:
            filename = os.path.basename(record.pathname) if record.pathname else "unknown"
            record.location = f"{filename}:{record.funcName}:{record.lineno}"

        # Add context fields if present
        context_parts = []
        if hasattr(record, 'context') and record.context:
            for key, value in record.context.items():
                context_parts.append(f"{key}={value}")
        # Add leading separator if context exists
        record.context_str = " | " + " ".join(context_parts) if context_parts else ""

        # Apply colors for console
        if self.use_colors and record.levelname in self.COLORS:
            record.levelname_colored = (
                f"{self.COLORS[record.levelname]}{record.levelname:8}{self.COLORS['RESET']}"
            )
        else:
            record.levelname_colored = f"{record.levelname:8}"

        return super().format(record)


# =============================================================================
# Context-Aware Logger
# =============================================================================

class AgentXLogger(logging.LoggerAdapter):
    """
    Logger adapter that supports structured context logging.

    Example:
        logger.info("Processing request", request_id="abc", user="john")
        # Output: 2024-01-04 12:00:00 | INFO | server.py:handler:42 | Processing request | request_id=abc user=john
    """

    def __init__(self, logger: logging.Logger, extra: Dict[str, Any] = None):
        super().__init__(logger, extra or {})

    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        # Extract context from kwargs
        context = {}
        extra = kwargs.get('extra', {})

        # Move non-standard kwargs to context
        standard_keys = {'exc_info', 'stack_info', 'stacklevel', 'extra'}
        for key in list(kwargs.keys()):
            if key not in standard_keys:
                context[key] = kwargs.pop(key)

        # Merge with adapter's extra
        context.update(self.extra)

        # Add context to extra
        extra['context'] = context
        kwargs['extra'] = extra

        return msg, kwargs

    def debug(self, msg: str, *args, **kwargs) -> None:
        """Log debug message with optional context."""
        self.log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        """Log info message with optional context."""
        self.log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        """Log warning message with optional context."""
        self.log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        """Log error message with optional context."""
        self.log(logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs) -> None:
        """Log critical message with optional context."""
        self.log(logging.CRITICAL, msg, *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs) -> None:
        """Log exception with traceback."""
        kwargs['exc_info'] = True
        self.log(logging.ERROR, msg, *args, **kwargs)


# =============================================================================
# Logger Factory
# =============================================================================

_initialized = False
_log_dir: Optional[str] = None
_log_level: int = logging.INFO
_root_logger: Optional[logging.Logger] = None


def configure_logging(
    log_level: str = "INFO",
    log_dir: Optional[str] = None,
    log_to_console: bool = True,
    log_to_file: bool = True,
    use_colors: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 7,
) -> None:
    """
    Configure the logging system. Should be called once at application startup.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files. Defaults to backend/logs/
        log_to_console: Whether to output logs to console
        log_to_file: Whether to write logs to file
        use_colors: Whether to use colors in console output
        max_bytes: Maximum size of each log file before rotation
        backup_count: Number of backup files to keep
    """
    global _initialized, _log_dir, _log_level, _root_logger

    if _initialized:
        return

    # Set log level
    _log_level = LOG_LEVELS.get(log_level.upper(), logging.INFO)

    # Set log directory
    if log_dir is None:
        _log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
    else:
        _log_dir = log_dir
    os.makedirs(_log_dir, exist_ok=True)

    # Get root logger for agentx
    _root_logger = logging.getLogger("agentx")
    _root_logger.setLevel(logging.DEBUG)  # Capture all, filter at handler level
    _root_logger.handlers.clear()  # Remove any existing handlers

    # Console format with colors
    console_format = "%(asctime)s | %(levelname_colored)s | %(location)s | %(message)s%(context_str)s"
    file_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(location)s | %(message)s%(context_str)s"

    # Console handler
    if log_to_console:
        # Handle Windows console encoding issues
        if hasattr(sys.stderr, "reconfigure"):
            try:
                sys.stderr.reconfigure(errors="replace")
            except Exception:
                pass
            console_stream = sys.stderr
        else:
            try:
                encoding = getattr(sys.stderr, "encoding", None) or "utf-8"
                console_stream = io.TextIOWrapper(
                    sys.stderr.buffer, encoding=encoding, errors="replace"
                )
            except Exception:
                console_stream = sys.stderr

        console_handler = logging.StreamHandler(console_stream)
        console_handler.setLevel(_log_level)
        console_formatter = AgentXFormatter(
            console_format,
            datefmt="%Y-%m-%d %H:%M:%S",
            use_colors=use_colors
        )
        console_handler.setFormatter(console_formatter)
        _root_logger.addHandler(console_handler)

    # File handler with rotation
    if log_to_file:
        log_file = os.path.join(_log_dir, "agentx.log")
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)  # File captures everything
        file_formatter = AgentXFormatter(
            file_format,
            datefmt="%Y-%m-%d %H:%M:%S",
            use_colors=False
        )
        file_handler.setFormatter(file_formatter)
        _root_logger.addHandler(file_handler)

    # Also capture logs from standard library modules we use
    for module_name in ["aiohttp", "anthropic", "sqlalchemy"]:
        module_logger = logging.getLogger(module_name)
        module_logger.setLevel(logging.WARNING)  # Only warnings and above

    _initialized = True


def get_logger(name: str = None) -> AgentXLogger:
    """
    Get a logger instance for the given module.

    Args:
        name: Module name (usually __name__). If None, returns root logger.

    Returns:
        AgentXLogger instance with context support

    Example:
        logger = get_logger(__name__)
        logger.info("Hello", user="world")
    """
    # Auto-configure if not done
    if not _initialized:
        configure_logging()

    # Create logger name
    if name:
        # Convert module path to logger name
        # e.g., "backend.agentx.api.server" -> "agentx.api.server"
        if name.startswith("backend."):
            name = name[8:]  # Remove "backend." prefix
        logger_name = f"agentx.{name}" if not name.startswith("agentx") else name
    else:
        logger_name = "agentx"

    # Get or create logger
    base_logger = logging.getLogger(logger_name)

    return AgentXLogger(base_logger)


# =============================================================================
# Convenience Functions (for quick access)
# =============================================================================

# Default logger instance
_default_logger: Optional[AgentXLogger] = None


def _get_default_logger() -> AgentXLogger:
    """Get the default logger instance."""
    global _default_logger
    if _default_logger is None:
        _default_logger = get_logger("default")
    return _default_logger


def debug(msg: str, **kwargs) -> None:
    """Log debug message using default logger."""
    _get_default_logger().debug(msg, **kwargs)


def info(msg: str, **kwargs) -> None:
    """Log info message using default logger."""
    _get_default_logger().info(msg, **kwargs)


def warning(msg: str, **kwargs) -> None:
    """Log warning message using default logger."""
    _get_default_logger().warning(msg, **kwargs)


def error(msg: str, **kwargs) -> None:
    """Log error message using default logger."""
    _get_default_logger().error(msg, **kwargs)


def critical(msg: str, **kwargs) -> None:
    """Log critical message using default logger."""
    _get_default_logger().critical(msg, **kwargs)


def exception(msg: str, **kwargs) -> None:
    """Log exception with traceback using default logger."""
    _get_default_logger().exception(msg, **kwargs)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Configuration
    "configure_logging",
    "get_logger",
    "AgentXLogger",
    "AgentXFormatter",
    # Convenience functions
    "debug",
    "info",
    "warning",
    "error",
    "critical",
    "exception",
    # Constants
    "LOG_LEVELS",
]
