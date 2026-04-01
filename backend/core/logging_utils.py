from __future__ import annotations

import logging
from typing import Any


def get_logger(name: str) -> Any:
    try:
        from loguru import logger as loguru_logger

        return loguru_logger
    except Exception:
        return logging.getLogger(name)

