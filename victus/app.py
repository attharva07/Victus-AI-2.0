from __future__ import annotations

"""Victus Phase 1 application scaffold.

This module wires together the router, planner, policy engine, executor, and
audit logger. It demonstrates the enforced flow: Input -> Plan -> Policy ->
Approval -> Execute -> Audit. Real interfaces (UI/voice/hotkey) will call into
`VictusApp.run_request` in later phases.
"""

import asyncio
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, Optional, Sequence

from .core.approval import issue_approval
from .core.audit import AuditLogger
from .core.confidence import ConfidenceEngine, ConfidenceLogger, ConfidencePlanEvaluation
from .core.failures import FailureEvent, FailureLogger, hash_stack, safe_user_intent
from .core.llm_health import get_llm_circuit_breaker
from .core.executor import ExecutionEngine
from .core.planner import Planner
from .core.policy import PolicyEngine
from .core.router import Router
from .core.sanitization import sanitize_plan
from .core.schemas import Approval, Context, IntentPlan, Plan, PlanStep, PolicyError, PrivacySettings, TurnEvent
from .domains.base import BasePlugin
from .config.runtime import get_llm_provider, is_outbound_llm_provider


class VictusApp:
    def __init__(
        self,
        plugins: Dict[str, BasePlugin],
        policy_engine: PolicyEngine | None = None,
        audit_logger: AuditLogger | None = None,
        *,
        context_factory: Callable[[], Context] | None = None,
        rule_router: Callable[[str, Context], Plan | None] | None = None,
        intent_planner: Callable[[str, Context], IntentPlan | Any] | None = None,
    ) -> None:
        self.router = Router()
        self.planner = Planner()
        self.policy_engine = policy_engine or PolicyEngine()
        self.executor = ExecutionEngine(plugins, signature_secret=self.policy_engine.signature_secret)
        self.audit = audit_logger or AuditLogger()
        self.failure_logger = FailureLogger(Path("victus/data/failures"))
        self.confidence_engine = ConfidenceEngine()
        self.confidence_logger = ConfidenceLogger(Path("victus/data/confidence"))
        self.context_factory = context_factory or self._default_context
        self.rule_router = rule_router
        self.intent_planner = intent_planner

    def build_plan(self, goal: str, domain: str, steps: Sequence[PlanStep], **kwargs) -> Plan:
        """Create a plan using the deterministic planner stub."""

        return self.planner.build_plan(goal=goal, domain=domain, steps=steps, **kwargs)

    def prepare_plan_for_policy(self, plan: Plan) -> Plan:
        """Mark outbound flows and redact sensitive arguments before policy review."""

        return sanitize_plan(plan)

    def request_approval(self, plan: Plan, context: Context) -> tuple[Plan, Approval]:
        """Prepare and submit a plan for approval, returning the redacted copy."""

        prepared_plan = self.prepare_plan_for_policy(plan)
        approval = issue_approval(prepared_plan, context, self.policy_engine)
        return prepared_plan, approval

    def execute_plan(self, plan: Plan, approval: Approval) -> Dict[str, object]:
        """Execute an approved plan via the execution engine."""

        return self.executor.execute(plan, approval)

    def execute_plan_streaming(
        self,
        plan: Plan,
        approval: Approval,
        *,
        stream_callbacks: Dict[str, Callable[[str], None]] | None = None,
        stop_requests: Dict[str, Callable[[], bool]] | None = None,
    ) -> Dict[str, object]:
        """Execute a plan while streaming results to provided callbacks."""

        return self.executor.execute_streaming(
            plan,
            approval,
            stream_callbacks=stream_callbacks,
            stop_requests=stop_requests,
        )

    async def run_request(
        self,
        user_input: str,
        *,
        context: Context | None = None,
        domain: str | None = None,
        steps: Sequence[PlanStep] | None = None,
        memory_prompt: str | None = None,
    ) -> AsyncIterator[TurnEvent]:
        """Run the unified request pipeline and stream structured events."""

        message = user_input.strip()
        if not message:
            yield TurnEvent(event="status", status="error")
            yield TurnEvent(event="error", message="Message is required.")
            return

        active_context = context or self.context_factory()
        yield TurnEvent(event="status", status="thinking")

        plan: Plan | None = None
        intent_plan: IntentPlan | None = None
        breaker = get_llm_circuit_breaker()
        try:
            if self.rule_router:
                plan = self.rule_router(message, active_context)
            else:
                plan = self.router.map_intent_to_plan(message)

            if plan is None and self.intent_planner:
                if not breaker.allow_request():
                    async for event in self._limited_mode_response():
                        yield event
                    return
                intent_plan = await self._resolve_intent_plan(message, active_context)

            if plan is None and intent_plan:
                if intent_plan.kind == "tool":
                    if not intent_plan.tool or not intent_plan.action:
                        raise ValueError("Intent planner returned incomplete tool data.")
                    step = PlanStep(
                        id="step-1",
                        tool=intent_plan.tool,
                        action=intent_plan.action,
                        args=intent_plan.args,
                    )
                    derived_domain = domain or self.policy_engine.tool_domains.get(intent_plan.tool, "productivity")
                    plan = Plan(goal=message, domain=derived_domain, steps=[step], risk="low", origin="planner")
                elif intent_plan.kind == "clarify":
                    yield TurnEvent(event="status", status="done")
                    yield TurnEvent(
                        event="clarify",
                        message=intent_plan.message or "Can you clarify what you want Victus to do?",
                    )
                    return

            if plan is None:
                if not breaker.allow_request():
                    async for event in self._limited_mode_response():
                        yield event
                    return
                plan_steps = steps or [
                    PlanStep(
                        id="openai-1",
                        tool="openai",
                        action="generate_text",
                        args={"prompt": message},
                    )
                ]
                plan_domain = domain or "productivity"
                plan = self.build_plan(goal=message, domain=plan_domain, steps=plan_steps)

            if self._plan_requires_llm(plan) and not breaker.allow_request():
                async for event in self._limited_mode_response():
                    yield event
                return

            if memory_prompt:
                for step in plan.steps:
                    if step.tool == "openai" and step.action in {"generate_text", "draft"}:
                        prompt = step.args.get("prompt")
                        if isinstance(prompt, str) and prompt.strip():
                            step.args["prompt"] = f"{memory_prompt}\n\nUser: {prompt}"
            confidence = self._evaluate_confidence(plan)
            if confidence.decision == "clarify":
                yield TurnEvent(event="status", status="done")
                yield TurnEvent(event="clarify", message=self.confidence_engine.build_clarification(confidence.primary))
                return
            if confidence.decision == "block":
                yield TurnEvent(event="status", status="denied")
                yield TurnEvent(event="error", message=self.confidence_engine.build_block_message(confidence.primary))
                return
            message = self._confidence_message(confidence)
            if message:
                yield TurnEvent(event="token", token=message, step_id=plan.steps[0].id)
            prepared_plan, approval = self.request_approval(plan, active_context)
        except PolicyError as exc:
            yield TurnEvent(event="status", status="denied")
            yield TurnEvent(event="error", message=str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            self._log_failure(message, active_context, domain or "productivity", steps or [], exc)
            yield TurnEvent(event="status", status="error")
            yield TurnEvent(event="error", message=str(exc))
            return

        yield TurnEvent(event="status", status="executing")
        for step in prepared_plan.steps:
            yield TurnEvent(
                event="tool_start",
                tool=step.tool,
                action=step.action,
                args=step.args,
                step_id=step.id,
            )

        token_queue: asyncio.Queue[TurnEvent] = asyncio.Queue()

        def _make_chunk_callback(step_id: str) -> Callable[[str], None]:
            def _callback(chunk: str) -> None:
                if chunk:
                    token_queue.put_nowait(TurnEvent(event="token", token=chunk, step_id=step_id))

            return _callback

        stream_callbacks: Dict[str, Callable[[str], None]] = {}
        for step in prepared_plan.steps:
            if step.tool == "openai" and step.action in {"generate_text", "draft"}:
                stream_callbacks[step.id] = _make_chunk_callback(step.id)

        async def _execute() -> Dict[str, object]:
            return await asyncio.to_thread(
                self.execute_plan_streaming,
                prepared_plan,
                approval,
                stream_callbacks=stream_callbacks,
            )

        execution_task = asyncio.create_task(_execute())

        while True:
            if execution_task.done() and token_queue.empty():
                break
            try:
                event = await asyncio.wait_for(token_queue.get(), timeout=0.1)
                yield event
            except asyncio.TimeoutError:
                continue

        try:
            results = await execution_task
        except Exception as exc:  # noqa: BLE001
            self._log_failure(message, active_context, plan.domain, plan.steps, exc)
            yield TurnEvent(event="status", status="error")
            yield TurnEvent(event="error", message=str(exc))
            return

        error_messages = []
        assistant_messages = []
        for step in prepared_plan.steps:
            result = results.get(step.id)
            if isinstance(result, dict) and result.get("error"):
                error_messages.append(str(result["error"]))
            if isinstance(result, dict):
                assistant_message = result.get("assistant_message")
                if isinstance(assistant_message, str) and assistant_message.strip():
                    assistant_messages.append(assistant_message.strip())
            yield TurnEvent(
                event="tool_done",
                tool=step.tool,
                action=step.action,
                result=result,
                step_id=step.id,
            )

        if assistant_messages:
            combined = "\n".join(assistant_messages)
            yield TurnEvent(event="token", token=combined, step_id=prepared_plan.steps[0].id)

        if error_messages:
            error_message = error_messages[0]
            yield TurnEvent(event="status", status="error")
            yield TurnEvent(event="error", message=error_message)
        else:
            yield TurnEvent(event="status", status="done")

        self.audit.log_request(
            user_input=message,
            plan=prepared_plan,
            approval=approval,
            results=results,
            errors="; ".join(error_messages) if error_messages else None,
        )

    def run_request_sync(self, user_input: str, context: Context, domain: str, steps: Sequence[PlanStep]) -> Dict[str, object]:
        """Run the full request lifecycle and record an audit entry."""

        try:
            breaker = get_llm_circuit_breaker()
            routed = self.router.route(user_input, context)
            if routed.plan:
                plan = routed.plan
            else:
                if not breaker.allow_request():
                    return {"error": "llm_unavailable", "message": self._limited_mode_message()}
                plan = self.build_plan(goal=user_input, domain=domain, steps=steps)
            if self._plan_requires_llm(plan) and not breaker.allow_request():
                return {"error": "llm_unavailable", "message": self._limited_mode_message()}
            confidence = self._evaluate_confidence(plan)
            if confidence.decision == "clarify":
                return {"error": "clarify", "message": self.confidence_engine.build_clarification(confidence.primary)}
            if confidence.decision == "block":
                return {"error": "blocked", "message": self.confidence_engine.build_block_message(confidence.primary)}
            prepared_plan, approval = self.request_approval(plan, routed.context)
            results = self.execute_plan(prepared_plan, approval)
            self.audit.log_request(
                user_input=user_input,
                plan=prepared_plan,
                approval=approval,
                results=results,
                errors=None,
            )
            return results
        except Exception as exc:  # noqa: BLE001
            self._log_failure(user_input, context, domain, steps, exc)
            if isinstance(exc, PolicyError):
                raise
            return {"error": "request_failed", "message": "The request could not be completed safely."}

    def run_request_streaming(
        self,
        user_input: str,
        context: Context,
        domain: str,
        steps: Sequence[PlanStep],
        *,
        stream_callbacks: Dict[str, Callable[[str], None]] | None = None,
        stop_requests: Dict[str, Callable[[], bool]] | None = None,
    ) -> Dict[str, object]:
        """Run the request lifecycle while streaming step outputs.

        This mirrors ``run_request`` but dispatches steps through
        ``execute_plan_streaming`` so that UI callers can append output
        incrementally without blocking the main thread.
        """

        try:
            breaker = get_llm_circuit_breaker()
            routed = self.router.route(user_input, context)
            if routed.plan:
                plan = routed.plan
            else:
                if not breaker.allow_request():
                    return {"error": "llm_unavailable", "message": self._limited_mode_message()}
                plan = self.build_plan(goal=user_input, domain=domain, steps=steps)
            if self._plan_requires_llm(plan) and not breaker.allow_request():
                return {"error": "llm_unavailable", "message": self._limited_mode_message()}
            confidence = self._evaluate_confidence(plan)
            if confidence.decision == "clarify":
                return {"error": "clarify", "message": self.confidence_engine.build_clarification(confidence.primary)}
            if confidence.decision == "block":
                return {"error": "blocked", "message": self.confidence_engine.build_block_message(confidence.primary)}
            prepared_plan, approval = self.request_approval(plan, routed.context)
            results = self.execute_plan_streaming(
                prepared_plan,
                approval,
                stream_callbacks=stream_callbacks,
                stop_requests=stop_requests,
            )
            self.audit.log_request(
                user_input=user_input,
                plan=prepared_plan,
                approval=approval,
                results=results,
                errors=None,
            )
            return results
        except Exception as exc:  # noqa: BLE001
            self._log_failure(user_input, context, domain, steps, exc)
            if isinstance(exc, PolicyError):
                raise
            return {"error": "request_failed", "message": "The request could not be completed safely."}

    @staticmethod
    def _mark_openai_outbound(plan: Plan) -> Plan:
        provider = get_llm_provider()
        is_outbound = is_outbound_llm_provider(provider)
        outbound = replace(
            plan.data_outbound,
            to_openai=is_outbound and any(step.tool == "openai" for step in plan.steps),
            redaction_required=is_outbound and plan.data_outbound.redaction_required,
        )
        return replace(plan, data_outbound=outbound)

    @staticmethod
    def _redact_value(key: str, value: object) -> object:
        if not isinstance(value, str):
            return value
        if key == "to":
            return "redacted@example.com"
        return "[REDACTED]"

    def _redact_openai_steps(self, plan: Plan) -> Plan:
        if not plan.data_outbound.redaction_required:
            return plan

        redacted_steps = []
        for step in plan.steps:
            if step.tool != "openai":
                redacted_steps.append(step)
                continue
            redacted_args = {key: self._redact_value(key, value) for key, value in step.args.items()}
            redacted_steps.append(replace(step, args=redacted_args))

        return replace(plan, steps=redacted_steps)

    def _log_failure(self, user_input: str, context: Context, domain: str, steps: Sequence[PlanStep], exc: Exception) -> None:
        action_name = steps[0].action if steps else "run_request"
        event = FailureEvent(
            stage="2",
            phase="1",
            domain=domain,
            component="executor",
            severity="high",
            category="runtime_error",
            request_id=getattr(context, "session_id", ""),
            user_intent=safe_user_intent(user_input),
            action={"name": action_name, "args_redacted": True},
            failure={
                "code": "request_pipeline_error",
                "message": safe_user_intent(str(exc)),
                "exception_type": exc.__class__.__name__,
                "stack_hash": hash_stack(exc),
                "details_redacted": True,
            },
            expected_behavior="Request should complete without uncaught exceptions",
            remediation_hint="Inspect recurring stack hashes and add guards",
            resolution={"status": "new", "resolved_ts": None, "notes": None},
            tags=[domain],
        )
        self.failure_logger.append(event)

    @staticmethod
    def _default_context() -> Context:
        return Context(
            session_id="victus-session",
            timestamp=datetime.utcnow(),
            mode="dev",
            foreground_app=None,
            privacy=PrivacySettings(allow_send_to_openai=True),
        )

    async def _resolve_intent_plan(self, message: str, context: Context) -> IntentPlan | None:
        if not self.intent_planner:
            return None
        result = self.intent_planner(message, context)
        if asyncio.iscoroutine(result):
            return await result
        return result  # type: ignore[return-value]

    @staticmethod
    def _serialize_event(event: TurnEvent) -> Dict[str, Any]:
        payload = asdict(event)
        return {key: value for key, value in payload.items() if value is not None}

    def _evaluate_confidence(self, plan: Plan) -> ConfidencePlanEvaluation:
        evaluation = self.confidence_engine.evaluate_plan(plan)
        for item in evaluation.evaluations:
            self.confidence_logger.append(item)
        return evaluation

    def _confidence_message(self, evaluation: ConfidencePlanEvaluation) -> Optional[str]:
        if evaluation.decision == "soft_confirm":
            return self.confidence_engine.build_soft_confirm_message(evaluation.primary)
        if evaluation.decision == "execute":
            return self.confidence_engine.build_execute_message(evaluation.primary)
        return None

    @staticmethod
    def _plan_requires_llm(plan: Plan) -> bool:
        return any(step.tool == "openai" for step in plan.steps)

    @staticmethod
    def _limited_mode_message() -> str:
        return "LLM is unavailable (limited mode). Try a direct command (e.g., 'open calculator')."

    async def _limited_mode_response(self) -> AsyncIterator[TurnEvent]:
        yield TurnEvent(event="status", status="done")
        yield TurnEvent(event="token", token=self._limited_mode_message())
