from __future__ import annotations

import os

import uvicorn

from core.config import ensure_directories
from core.logging.logger import get_logger


def main() -> None:
    ensure_directories()
    logger = get_logger()
    host = os.getenv("VICTUS_LOCAL_HOST", "127.0.0.1")
    port = int(os.getenv("VICTUS_LOCAL_PORT", "8000"))
    logger.info("Starting Victus Local on %s:%s", host, port)
    uvicorn.run("apps.local.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
