from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .app_resolver import ResolvedCandidate


@dataclass
class PendingAction:
    kind: str
    original_text: str
    candidates: List[ResolvedCandidate] = field(default_factory=list)
    created_at: float = 0.0


@dataclass
class DialogueState:
    pending: Optional[PendingAction] = None
