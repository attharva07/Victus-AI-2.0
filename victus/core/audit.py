from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .sanitization import sanitize_plan
from .schemas import Approval, Plan


@dataclass
class AuditRecord:
    user_input: str
    plan: Plan
    approval: Optional[Approval]
    results: Optional[Dict[str, Any]]
    errors: Optional[str]
    redacted_secrets: List[str] = field(default_factory=list)


class AuditLogger:
    def __init__(self) -> None:
        self.records: List[AuditRecord] = []

    def log_request(
        self,
        user_input: str,
        plan: Plan,
        approval: Optional[Approval],
        results: Optional[Dict[str, Any]],
        errors: Optional[str],
        secrets: Optional[List[str]] = None,
    ) -> AuditRecord:
        redacted = ["[REDACTED]" for _ in secrets or []]
        sanitized_plan = sanitize_plan(plan)
        record = AuditRecord(
            user_input=user_input,
            plan=sanitized_plan,
            approval=approval,
            results=results,
            errors=errors,
            redacted_secrets=redacted,
        )
        self.records.append(record)
        return record
