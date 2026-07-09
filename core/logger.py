"""
core/logger.py

Centralized logging configuration for liquiditybot.
Logs to both console and a rotating file under outputs/logs/.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "outputs" / "logs"
LOG_FILE = LOG_DIR / "liquiditybot.log"


def setup_logger(level: str = "INFO") -> logging.Logger:
    """
    Configure the root 'liquiditybot' logger with console + rotating file handlers.
    Safe to call once at startup (main.py). Idempotent if called again.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("liquiditybot")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Avoid duplicate handlers if setup_logger is called more than once
    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=5_000_000, backupCount=5
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger
