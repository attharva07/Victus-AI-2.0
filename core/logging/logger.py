from __future__ import annotations

import logging
from typing import Optional


_LOGGER: Optional[logging.Logger] = None


def get_logger() -> logging.Logger:
    global _LOGGER
    if _LOGGER is None:
        logger = logging.getLogger("victus")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s",
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        _LOGGER = logger
    return _LOGGER
