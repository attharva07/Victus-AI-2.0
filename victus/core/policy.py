from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Dict, Iterable, List, Optional, Set

from .schemas import Approval, ApprovalConstraints, Context, Plan, PlanStep, PolicyError


class PolicyEngine:
    def __init__(
        self,
        allowlist: Optional[Dict[str, Set[str]]] = None,
        denylist: Optional[Iterable[str]] = None,
        signature_secret: str = "signed-policy",
    ) -> None:
        self.allowlist = allowlist or {
            "system": {"open_app", "net_snapshot"},
            "spotify": {"play"},
            "gmail": {"send"},
            "openai": {"draft", "draft_email", "summarize_text"},
            "docs": {"create"},
        }
        self.tool_domains: Dict[str, str] = {
            "system": "system",
            "spotify": "productivity",
            "gmail": "productivity",
            "openai": "productivity",
            "docs": "productivity",
        }
        self.denylist: Set[str] = set(denylist or {"raw_shell", "kernel_exec", "firewall_modify"})
        self.signature_secret = signature_secret

    def evaluate(self, plan: Plan, context: Context) -> Approval:
        self.enforce_plan_domain(plan)
        self._enforce_plan_rules(plan, context)
        requires_confirmation = plan.requires_confirmation or plan.risk in {"medium", "high"}
        if self._requires_gmail_confirmation(plan):
            requires_confirmation = True

        constraints = ApprovalConstraints(
            time_limit_sec=30,
            no_screenshot_store=not context.privacy.allow_store_images,
            redact_before_openai=plan.data_outbound.redaction_required,
        )

        approved_steps: List[str] = [step.id for step in plan.steps]
        signature = compute_policy_signature(
            plan=plan,
            approved_steps=approved_steps,
            constraints=constraints,
            requires_confirmation=requires_confirmation,
            secret=self.signature_secret,
        )

        return Approval(
            approved=True,
            approved_steps=approved_steps,
            requires_confirmation=requires_confirmation,
            constraints=constraints,
            policy_signature=signature,
        )

    def _enforce_plan_rules(self, plan: Plan, context: Context) -> None:
        requires_openai_opt_in = plan.data_outbound.to_openai or any(step.tool == "openai" for step in plan.steps)
        if requires_openai_opt_in and not context.privacy.allow_send_to_openai:
            raise PolicyError("Outbound data to OpenAI not permitted by privacy settings")

        for step in plan.steps:
            self._validate_step(step)
            if step.tool == "system":
                self._validate_system_action(step)
            if step.inputs.uses_screenshot and not context.privacy.allow_screenshot:
                raise PolicyError("Screenshots are not permitted in current privacy context")

    def _validate_step(self, step: PlanStep) -> None:
        fully_qualified = f"{step.tool}.{step.action}"
        if fully_qualified in self.denylist or step.action in self.denylist:
            raise PolicyError(f"Action '{fully_qualified}' is denylisted")
        if step.tool not in self.allowlist:
            raise PolicyError(f"Unknown tool '{step.tool}' is not allowlisted")
        if step.action not in self.allowlist.get(step.tool, set()):
            raise PolicyError(f"Action '{fully_qualified}' is not allowlisted")
        if not self._is_domain_permitted(step.tool):
            raise PolicyError(f"Tool '{step.tool}' is not permitted in its declared domain")

    def _validate_system_action(self, step: PlanStep) -> None:
        fully_qualified = f"{step.tool}.{step.action}"
        if step.action not in self.allowlist.get("system", set()):
            raise PolicyError(f"System action '{fully_qualified}' is not allowlisted")

    @staticmethod
    def _requires_gmail_confirmation(plan: Plan) -> bool:
        return any(step.tool == "gmail" and step.action == "send" for step in plan.steps)

    def _is_domain_permitted(self, tool: str) -> bool:
        tool_domain = self.tool_domains.get(tool)
        return tool_domain in {"system", "productivity"}

    def enforce_plan_domain(self, plan: Plan) -> None:
        for step in plan.steps:
            tool_domain = self.tool_domains.get(step.tool)
            if tool_domain is None:
                raise PolicyError(f"Unknown tool '{step.tool}' is not mapped to a domain")
            if plan.domain == "mixed":
                continue
            if plan.domain == "system" and tool_domain != "system":
                raise PolicyError("Productivity tool used inside a system-only plan")
            if plan.domain == "productivity" and tool_domain != "productivity":
                raise PolicyError("System tool used inside a productivity-only plan")


def compute_policy_signature(
    plan: Plan,
    approved_steps: List[str],
    constraints: ApprovalConstraints,
    requires_confirmation: bool,
    secret: str,
) -> str:
    """Generate a deterministic signature bound to the plan and approval details."""

    payload = {
        "plan": {
            "goal": plan.goal,
            "domain": plan.domain,
            "risk": plan.risk,
            "requires_confirmation": plan.requires_confirmation,
            "data_outbound": asdict(plan.data_outbound),
            "steps": [
                {
                    "id": step.id,
                    "tool": step.tool,
                    "action": step.action,
                    "args": step.args,
                    "inputs": asdict(step.inputs),
                    "outputs": asdict(step.outputs),
                }
                for step in plan.steps
            ],
        },
        "approved_steps": approved_steps,
        "approval_requires_confirmation": requires_confirmation,
        "constraints": asdict(constraints),
        "secret": secret,
    }
    serialized = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()
