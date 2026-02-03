from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UpdateStatus:
    available: bool
    version: str | None = None


def check_for_updates() -> UpdateStatus:
    return UpdateStatus(available=False)


def apply_update() -> None:
    return None
