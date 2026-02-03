from __future__ import annotations

from pathlib import Path

from core.config import ensure_directories
from core.vault.sandbox import VaultPathError, safe_join

ALLOWED_EXTENSIONS = {".txt", ".md", ".json", ".csv"}
MAX_READ_BYTES = 1_048_576


class FileSandboxError(ValueError):
    pass


def _base_dir() -> Path:
    paths = ensure_directories()
    return paths.file_sandbox_dir


def _validate_extension(path: Path) -> None:
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise FileSandboxError("File extension not allowed")


def _resolve_path(rel_path: str) -> Path:
    if not rel_path:
        raise FileSandboxError("Path is required")
    try:
        resolved = safe_join(_base_dir(), rel_path)
    except VaultPathError as exc:
        raise FileSandboxError(str(exc)) from exc
    _validate_extension(resolved)
    return resolved


def list_files() -> list[str]:
    base = _base_dir()
    results: list[str] = []
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        if path.is_symlink():
            continue
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        resolved = path.resolve()
        try:
            resolved.relative_to(base.resolve())
        except ValueError:
            continue
        results.append(str(resolved.relative_to(base)))
    return sorted(results)


def read_file(rel_path: str) -> str:
    resolved = _resolve_path(rel_path)
    if not resolved.exists():
        raise FileSandboxError("File not found")
    size = resolved.stat().st_size
    if size > MAX_READ_BYTES:
        raise FileSandboxError("File too large to read")
    return resolved.read_text(encoding="utf-8")


def write_file(rel_path: str, content: str, mode: str = "overwrite") -> None:
    resolved = _resolve_path(rel_path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    if mode not in {"overwrite", "append"}:
        raise FileSandboxError("Invalid write mode")
    if mode == "append":
        resolved.open("a", encoding="utf-8").write(content)
    else:
        resolved.write_text(content, encoding="utf-8")
