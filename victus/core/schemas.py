from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class PrivacySettings:
    allow_screenshot: bool = False
    allow_send_to_openai: bool = False
    allow_store_images: bool = False


@dataclass
class Context:
    session_id: str
    timestamp: datetime
    mode: str
    foreground_app: Optional[str]
    user_confirmed: bool = False
    privacy: PrivacySettings = field(default_factory=PrivacySettings)

    def __post_init__(self) -> None:
        if self.mode not in {"prod", "dev"}:
            raise ValueError("mode must be 'prod' or 'dev'")


@dataclass
class StepIO:
    uses_screenshot: bool = False
    uses_user_text: bool = True


@dataclass
class StepOutputs:
    produces_text: bool = True
    produces_side_effect: bool = False


@dataclass
class PlanStep:
    id: str
    tool: str
    action: str
    args: Dict[str, Any] = field(default_factory=dict)
    inputs: StepIO = field(default_factory=StepIO)
    outputs: StepOutputs = field(default_factory=StepOutputs)


@dataclass
class DataOutbound:
    to_openai: bool = False
    content_types: List[str] = field(default_factory=lambda: ["text"])
    redaction_required: bool = True


@dataclass
class Plan:
    goal: str
    domain: str
    steps: List[PlanStep]
    requires_confirmation: bool = False
    data_outbound: DataOutbound = field(default_factory=DataOutbound)
    risk: str = "low"
    notes: str = ""

    def __post_init__(self) -> None:
        if self.domain not in {"system", "productivity", "mixed"}:
            raise ValueError("domain must be system, productivity, or mixed")
        if self.risk not in {"low", "medium", "high"}:
            raise ValueError("risk must be low, medium, or high")
        if not self.steps:
            raise ValueError("Plan must include at least one step")


@dataclass
class ApprovalConstraints:
    time_limit_sec: int = 30
    no_screenshot_store: bool = True
    redact_before_openai: bool = True


@dataclass
class Approval:
    approved: bool
    approved_steps: List[str] = field(default_factory=list)
    requires_confirmation: bool = False
    constraints: ApprovalConstraints = field(default_factory=ApprovalConstraints)
    policy_signature: str = ""


class PolicyError(Exception):
    """Raised when a plan violates policy."""


class ExecutionError(Exception):
    """Raised when execution preconditions are not met."""
