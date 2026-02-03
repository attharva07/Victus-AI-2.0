from __future__ import annotations

from core.filesystem.sandbox import read_file, write_file, list_files
from core.logging.audit import audit_event


def list_sandbox_files() -> list[str]:
    files = list_files()
    audit_event("files_listed", count=len(files))
    return files


def read_sandbox_file(path: str) -> str:
    content = read_file(path)
    audit_event("files_read", path=path)
    return content


def write_sandbox_file(path: str, content: str, mode: str = "overwrite") -> None:
    write_file(path, content, mode)
    audit_event("files_written", path=path, mode=mode, size=len(content))
