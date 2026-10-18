"""
Logging configuration — sets up the root logger for the entire application.
Import this module early (in main.py) so all subsequent loggers inherit the format.
"""

import logging


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger with timestamp, module name, and level."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


# Convenience: module-level logger for core internals
logger = logging.getLogger("bot")
