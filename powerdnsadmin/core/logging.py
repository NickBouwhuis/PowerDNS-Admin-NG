"""
Module-level logger for use in models and other framework-agnostic code.

Replaces current_app.logger references throughout the codebase.
"""
import logging
import os


def get_logger(name: str = None) -> logging.Logger:
    """Get a named logger under the powerdnsadmin namespace."""
    if name:
        return logging.getLogger(f"powerdnsadmin.{name}")
    return logging.getLogger("powerdnsadmin")


def setup_logging() -> None:
    """Configure root logging based on environment variables."""
    log_level_name = os.environ.get('PDNS_ADMIN_LOG_LEVEL', 'WARNING')
    log_level = logging.getLevelName(log_level_name.upper())
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] [%(filename)s:%(lineno)d] %(levelname)s - %(message)s",
    )
