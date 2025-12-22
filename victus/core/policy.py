from __future__ import annotations

from typing import Dict, Iterable, Optional, Set

from .schemas import Approval, ApprovalConstraints, Context, Plan, PlanStep, PolicyError


class PolicyEngine:
    def __init__(
        self,
        allowlist: Optional[Dict[str, Set[str]]] = None,
        denylist: Optional[Iterable[str]] = None,
        signature: str = "signed-policy",
    ) -> None:
        self.allowlist = allowlist or {
            "system": {"open_app", "net_snapshot"},
            "spotify": {"play"},
            "gmail": {"send"},
            "openai": {"draft"},
            "docs": {"create"},
        }
        self.denylist: Set[str] = set(denylist or {"raw_shell", "kernel_exec", "firewall_modify"})
        self.signature = signature

    def evaluate(self, plan: Plan, context: Context) -> Approval:
        self._enforce_plan_rules(plan, context)
        requires_confirmation = plan.requires_confirmation or plan.risk in {"medium", "high"}
        if self._requires_gmail_confirmation(plan):
            requires_confirmation = True

        constraints = ApprovalConstraints(
            time_limit_sec=30,
            no_screenshot_store=not context.privacy.allow_store_images,
            redact_before_openai=plan.data_outbound.redaction_required,
        )

        return Approval(
            approved=True,
            approved_steps=[step.id for step in plan.steps],
            requires_confirmation=requires_confirmation,
            constraints=constraints,
            policy_signature=self.signature,
        )

    def _enforce_plan_rules(self, plan: Plan, context: Context) -> None:
        if plan.data_outbound.to_openai and not context.privacy.allow_send_to_openai:
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

    def _validate_system_action(self, step: PlanStep) -> None:
        fully_qualified = f"{step.tool}.{step.action}"
        if step.action not in self.allowlist.get("system", set()):
            raise PolicyError(f"System action '{fully_qualified}' is not allowlisted")

    @staticmethod
    def _requires_gmail_confirmation(plan: Plan) -> bool:
        return any(step.tool == "gmail" and step.action == "send" for step in plan.steps)
