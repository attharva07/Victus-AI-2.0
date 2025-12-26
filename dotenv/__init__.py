from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable


def load_dotenv(dotenv_path: str | os.PathLike[str] | None = None, override: bool = False) -> bool:
    """Load environment variables from a .env file.

    This is a lightweight, compatible subset of python-dotenv's load_dotenv API
    to support environments where the dependency is not preinstalled.
    """

    path = Path(dotenv_path) if dotenv_path else Path.cwd() / ".env"
    if not path.exists():
        return False

    for key, value in _parse_env_lines(path.read_text().splitlines()):
        if not override and key in os.environ:
            continue
        os.environ[key] = value

    return True


def _parse_env_lines(lines: Iterable[str]) -> Iterable[tuple[str, str]]:
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        yield key.strip(), value.strip().strip('"').strip("'")
