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
    file_sandbox_dir: Path


@dataclass(frozen=True)
class CameraConfig:
    enabled: bool
    backend: str
    device_index: int
    max_image_bytes: int
    max_dim: int


@dataclass(frozen=True)
class OrchestratorConfig:
    enable_llm_fallback: bool
    llm_enabled: bool
    llm_provider: str
    llm_allow_autoexec: bool
    llm_autoexec_min_confidence: float


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
    file_sandbox_dir = Path(os.getenv("VICTUS_FILE_SANDBOX_DIR", data_dir / "sandbox_files")).expanduser()
    return LocalPaths(
        base_dir=base_dir,
        data_dir=data_dir,
        logs_dir=logs_dir,
        vault_dir=vault_dir,
        file_sandbox_dir=file_sandbox_dir,
    )


def ensure_directories() -> LocalPaths:
    paths = get_local_paths()
    for path in (
        paths.base_dir,
        paths.data_dir,
        paths.logs_dir,
        paths.vault_dir,
        paths.file_sandbox_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
    return paths


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def get_camera_config() -> CameraConfig:
    enabled = _parse_bool(os.getenv("VICTUS_CAMERA_ENABLED"), False)
    backend = os.getenv("VICTUS_CAMERA_BACKEND", "stub").strip().lower()
    if backend not in {"stub", "opencv"}:
        backend = "stub"
    device_index = _parse_int(os.getenv("VICTUS_CAMERA_DEVICE_INDEX"), 0)
    max_image_bytes = _parse_int(os.getenv("VICTUS_CAMERA_MAX_IMAGE_BYTES"), 2_000_000)
    max_dim = _parse_int(os.getenv("VICTUS_CAMERA_MAX_DIM"), 1280)
    return CameraConfig(
        enabled=enabled,
        backend=backend,
        device_index=device_index,
        max_image_bytes=max_image_bytes,
        max_dim=max_dim,
    )


def _parse_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def get_orchestrator_config() -> OrchestratorConfig:
    llm_enabled = _parse_bool(os.getenv("VICTUS_LLM_ENABLED"), False)
    # Legacy compatibility: fallback env still enables proposer path if set.
    legacy_fallback = _parse_bool(os.getenv("VICTUS_ENABLE_LLM_FALLBACK"), False)
    llm_provider = os.getenv("VICTUS_LLM_PROVIDER", "stub").strip().lower() or "stub"
    return OrchestratorConfig(
        enable_llm_fallback=(llm_enabled or legacy_fallback),
        llm_enabled=llm_enabled,
        llm_provider=llm_provider,
        llm_allow_autoexec=_parse_bool(os.getenv("VICTUS_LLM_ALLOW_AUTOEXEC"), False),
        llm_autoexec_min_confidence=_parse_float(os.getenv("VICTUS_LLM_AUTOEXEC_MIN_CONFIDENCE"), 0.90),
    )
