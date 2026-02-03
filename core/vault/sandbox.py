from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional


class VaultPathError(ValueError):
    pass


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _check_allowlist(relative_parts: tuple[str, ...], allowlist: Optional[Iterable[str]]) -> None:
    if allowlist is None:
        return
    if not relative_parts:
        raise VaultPathError("Empty path not allowed")
    allowed = {item.strip("/") for item in allowlist}
    if relative_parts[0] not in allowed:
        raise VaultPathError("Path not in allowlist")


def _check_symlinks(candidate: Path, base: Path) -> None:
    current = base
    for part in candidate.relative_to(base).parts:
        current = current / part
        if current.is_symlink():
            resolved = current.resolve()
            if not _is_relative_to(resolved, base):
                raise VaultPathError("Symlink escape detected")


def safe_join(base_dir: Path, *paths: str, allowlist: Optional[Iterable[str]] = None) -> Path:
    base_dir = base_dir.resolve()
    candidate = base_dir.joinpath(*paths)
    try:
        relative_parts = candidate.relative_to(base_dir).parts
    except ValueError as exc:
        raise VaultPathError("Path traversal detected") from exc
    _check_allowlist(relative_parts, allowlist)
    resolved = candidate.resolve()
    if not _is_relative_to(resolved, base_dir):
        raise VaultPathError("Path traversal detected")
    _check_symlinks(candidate, base_dir)
    return resolved
