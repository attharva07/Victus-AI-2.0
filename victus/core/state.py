from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from .schemas import Approval, Plan


@dataclass
class SessionState:
    """Simple in-memory state carrier for Phase 1 scaffolding."""

    last_plan: Optional[Plan] = None
    last_approval: Optional[Approval] = None
    metadata: Dict[str, str] = field(default_factory=dict)
