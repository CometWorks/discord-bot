"""Logging setup."""

from __future__ import annotations

import logging
import sys
import time
from logging import Formatter, StreamHandler
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
LOG_DIR = BASE_DIR / "logs"
SPAM_DIR = BASE_DIR / "spam"

simple_formatter = Formatter(
    "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S"
)

colored_formatter = Formatter(
    (
        "\033[90m%(asctime)s\033[0m "
        "\033[34m%(levelname)-8s\033[0m "
        "\033[32m%(name)-22s \033[0m %(message)s"
    ),
    "%Y-%m-%d %H:%M:%S",
)


def setup_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    SPAM_DIR.mkdir(exist_ok=True)
    logging.Formatter.converter = time.gmtime

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if root_logger.handlers:
        return

    console_handler = StreamHandler(sys.stdout)
    console_handler.setFormatter(colored_formatter)

    file_handler = TimedRotatingFileHandler(
        LOG_DIR / "info.log",
        backupCount=30,
        when="midnight",
        encoding="utf-8",
    )
    file_handler.setFormatter(simple_formatter)
    file_handler.suffix = "%Y%m%d"

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
