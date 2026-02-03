from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LocalPaths:
    base_dir: Path
    data_dir: Path
    logs_dir: Path
    vault_dir: Path


def _default_base_dir() -> Path:
    override = os.getenv("VICTUS_DATA_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        root = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return root / "VictusAI"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "VictusAI"
    root = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / "victus_ai"


def get_local_paths() -> LocalPaths:
    base_dir = _default_base_dir()
    data_dir = base_dir / "data"
    logs_dir = base_dir / "logs"
    vault_dir = base_dir / "vault"
    return LocalPaths(base_dir=base_dir, data_dir=data_dir, logs_dir=logs_dir, vault_dir=vault_dir)


def ensure_directories() -> LocalPaths:
    paths = get_local_paths()
    for path in (paths.base_dir, paths.data_dir, paths.logs_dir, paths.vault_dir):
        path.mkdir(parents=True, exist_ok=True)
    return paths
