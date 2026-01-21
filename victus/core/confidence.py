from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from .schemas import Plan, PlanStep
from .util.jsonl import append_jsonl


@dataclass(frozen=True)
class ParsedIntent:
    intent: str
    provider: Optional[str] = None
    query: Optional[str] = None
    artist: Optional[str] = None


@dataclass(frozen=True)
class IntentSpec:
    intent: str
    required_fields: Tuple[str, ...] = ()
    optional_fields: Tuple[str, ...] = ()
    provider: Optional[str] = None
    query_field: Optional[str] = None
    artist_field: Optional[str] = None


@dataclass
class ConfidenceEvaluation:
    intent: str
    parse: float
    retrieval: float
    final: float
    decision: str
    reasons: List[str]
    tool: Optional[str] = None
    action: Optional[str] = None
    missing_fields: List[str] = field(default_factory=list)

    def to_log(self) -> Dict[str, object]:
        return {
            "type": "confidence_eval",
            "intent": self.intent,
            "parse": self.parse,
            "retrieval": self.retrieval,
            "final": self.final,
            "decision": self.decision,
        }


@dataclass
class ConfidencePlanEvaluation:
    decision: str
    final: float
    evaluations: List[ConfidenceEvaluation]
    primary: ConfidenceEvaluation


class ConfidenceLogger:
    def __init__(self, base_dir: Path) -> None:
        base_dir.mkdir(parents=True, exist_ok=True)
        self.path = base_dir / "confidence.jsonl"

    def append(self, evaluation: ConfidenceEvaluation) -> None:
        append_jsonl(self.path, evaluation.to_log())


IntentRetrieval = Callable[[ParsedIntent], float]


class ConfidenceEngine:
    def __init__(self, retrieval_providers: Optional[Dict[str, IntentRetrieval]] = None) -> None:
        self.retrieval_providers = retrieval_providers or {}

    def evaluate_plan(self, plan: Plan) -> ConfidencePlanEvaluation:
        evaluations = [self.evaluate_step(step) for step in plan.steps]
        primary = min(evaluations, key=lambda item: item.final)
        return ConfidencePlanEvaluation(
            decision=primary.decision,
            final=primary.final,
            evaluations=evaluations,
            primary=primary,
        )

    def evaluate_step(self, step: PlanStep) -> ConfidenceEvaluation:
        spec = _INTENT_SPECS.get((step.tool, step.action))
        parsed_intent = self._build_parsed_intent(step, spec)
        missing_fields, required_present = self._check_required_fields(step, spec)

        parse_conf, parse_reasons = self._score_parse_conf(
            spec,
            step.args,
            required_present,
            missing_fields,
        )
        retrieval_conf, retrieval_reasons = self._score_retrieval_conf(
            parse_conf,
            parsed_intent,
            spec,
            required_present,
            missing_fields,
        )
        final_conf = _clamp(0.6 * parse_conf + 0.4 * retrieval_conf)
        decision = _decision_for(final_conf)
        if spec and missing_fields and not required_present:
            decision = "clarify" if _has_meaningful_input(step.args) else "block"

        reasons = parse_reasons + retrieval_reasons
        if not reasons:
            reasons.append("confidence computed")

        return ConfidenceEvaluation(
            intent=parsed_intent.intent,
            parse=parse_conf,
            retrieval=retrieval_conf,
            final=final_conf,
            decision=decision,
            reasons=reasons,
            tool=step.tool,
            action=step.action,
            missing_fields=missing_fields,
        )

    def build_clarification(self, evaluation: ConfidenceEvaluation) -> str:
        if evaluation.missing_fields:
            field = evaluation.missing_fields[0]
            return _FIELD_QUESTIONS.get(field, f"Please provide '{field}' to proceed.")
        return "Can you clarify what you want Victus to do?"

    @staticmethod
    def build_soft_confirm_message(evaluation: ConfidenceEvaluation) -> str:
        action = "unknown action"
        if evaluation.tool and evaluation.action:
            action = f"{evaluation.tool}.{evaluation.action}"
        return (
            "Proceeding with "
            f"{action} because confidence is {evaluation.final:.2f} "
            f"(parse {evaluation.parse:.2f}, retrieval {evaluation.retrieval:.2f})."
        )

    @staticmethod
    def build_execute_message(evaluation: ConfidenceEvaluation) -> str:
        action = "unknown action"
        if evaluation.tool and evaluation.action:
            action = f"{evaluation.tool}.{evaluation.action}"
        return f"Executing {action}."

    def build_block_message(self, evaluation: ConfidenceEvaluation) -> str:
        if evaluation.missing_fields:
            missing = ", ".join(evaluation.missing_fields)
            return f"Cannot execute safely yet. Missing: {missing}. Please rephrase with the details."
        return "Cannot execute safely with the current input. Please rephrase with more detail."

    def _build_parsed_intent(self, step: PlanStep, spec: IntentSpec | None) -> ParsedIntent:
        if not spec:
            return ParsedIntent(intent="unknown")
        provider = spec.provider or step.tool
        query = _extract_text_field(step.args, spec.query_field)
        artist = _extract_text_field(step.args, spec.artist_field)
        return ParsedIntent(intent=spec.intent, provider=provider, query=query, artist=artist)

    def _check_required_fields(self, step: PlanStep, spec: IntentSpec | None) -> Tuple[List[str], bool]:
        if not spec:
            return [], False
        if not spec.required_fields:
            return [], True
        missing = [field for field in spec.required_fields if not _is_field_present(step.args.get(field))]
        return missing, not missing

    def _score_parse_conf(
        self,
        spec: IntentSpec | None,
        args: Dict[str, object],
        required_present: bool,
        missing_fields: Iterable[str],
    ) -> Tuple[float, List[str]]:
        score = 0.0
        reasons: List[str] = []
        if spec:
            score += 0.40
            reasons.append(f"intent matched {spec.intent}")
        else:
            reasons.append("unknown intent grammar")

        if required_present:
            score += 0.30
            reasons.append("required fields present")
        else:
            reasons.append(f"missing required fields: {', '.join(missing_fields)}")
            reasons.append("missing required fields; clarification required")

        if spec and required_present:
            score += 0.20
            reasons.append("provider specified or defaulted")
        elif spec:
            reasons.append("provider deferred until required fields present")
        else:
            reasons.append("provider missing")

        if spec and spec.optional_fields and required_present:
            if any(_is_field_present(args.get(field_name)) for field_name in spec.optional_fields):
                score += 0.10
                reasons.append("optional clarity present")
            else:
                reasons.append("optional clarity missing")

        if not required_present:
            score = min(score, 0.34)

        return _clamp(score), reasons

    def _score_retrieval_conf(
        self,
        parse_conf: float,
        parsed_intent: ParsedIntent,
        spec: IntentSpec | None,
        required_present: bool,
        missing_fields: Iterable[str],
    ) -> Tuple[float, List[str]]:
        reasons: List[str] = []
        if not required_present and list(missing_fields):
            reasons.append("missing required fields; retrieval skipped")
            return parse_conf, reasons
        if parse_conf < 0.4:
            reasons.append("parse confidence below retrieval threshold")
            return parse_conf, reasons

        if not spec:
            reasons.append("retrieval skipped for unknown intent")
            return parse_conf, reasons

        provider = self.retrieval_providers.get(spec.intent)
        if provider is None:
            reasons.append("retrieval skipped (not configured)")
            return parse_conf, reasons

        try:
            retrieval_conf = provider(parsed_intent)
        except Exception as exc:  # noqa: BLE001
            reasons.append(f"retrieval failed: {exc}")
            return 0.0, reasons

        reasons.append("retrieval completed")
        return _clamp(retrieval_conf), reasons


_FIELD_QUESTIONS = {
    "track": "What track should I play?",
    "query": "What track should I play?",
    "artist": "Which artist should I use?",
    "to": "Who should I email?",
    "subject": "What is the email subject?",
    "body": "What should the email say?",
    "title": "What should the document be titled?",
    "content": "What content should the document include?",
    "prompt": "What should I draft?",
    "text": "What text should I summarize?",
    "topic": "What topic should I outline?",
    "app": "Which app should I open?",
    "detail": "Which network detail should I return?",
    "focus": "Which system focus should I check (cpu, memory, disk)?",
}


_INTENT_SPECS: Dict[Tuple[str, str], IntentSpec] = {
    ("spotify", "play"): IntentSpec(
        intent="media.play",
        required_fields=("track",),
        optional_fields=("artist",),
        provider="spotify",
        query_field="track",
        artist_field="artist",
    ),
    ("local", "media_play"): IntentSpec(
        intent="media.play",
        required_fields=("query",),
        optional_fields=("artist",),
        query_field="query",
        artist_field="artist",
    ),
    ("local", "media_stop"): IntentSpec(
        intent="media.stop",
        optional_fields=("provider",),
    ),
    ("system", "status"): IntentSpec(intent="system.status", optional_fields=("focus",)),
    ("system", "net_snapshot"): IntentSpec(intent="system.net_snapshot", optional_fields=("detail",)),
    ("system", "net_connections"): IntentSpec(intent="system.net_connections"),
    ("system", "exposure_snapshot"): IntentSpec(intent="system.exposure_snapshot"),
    ("system", "bt_status"): IntentSpec(intent="system.bt_status"),
    ("system", "local_devices"): IntentSpec(intent="system.local_devices"),
    ("system", "access_overview"): IntentSpec(intent="system.access_overview"),
    ("system", "open_app"): IntentSpec(
        intent="system.open_app",
        required_fields=("app",),
        optional_fields=("app",),
    ),
    ("local", "open_app"): IntentSpec(
        intent="local.open_app",
        required_fields=("app",),
        optional_fields=("app",),
    ),
    ("local", "open_youtube"): IntentSpec(intent="local.open_youtube"),
    ("gmail", "send"): IntentSpec(
        intent="communication.send_email",
        required_fields=("to", "subject", "body"),
        optional_fields=("subject",),
        provider="gmail",
    ),
    ("docs", "create"): IntentSpec(
        intent="docs.create",
        required_fields=("title", "content"),
        optional_fields=("title",),
        provider="docs",
    ),
    ("openai", "draft"): IntentSpec(
        intent="assistant.generate_text",
        required_fields=("prompt",),
        provider="openai",
        query_field="prompt",
    ),
    ("openai", "generate_text"): IntentSpec(
        intent="assistant.generate_text",
        required_fields=("prompt",),
        provider="openai",
        query_field="prompt",
    ),
    ("openai", "draft_email"): IntentSpec(
        intent="assistant.draft_email",
        required_fields=("to", "subject", "body"),
        provider="openai",
    ),
    ("openai", "summarize"): IntentSpec(
        intent="assistant.summarize",
        required_fields=("text",),
        provider="openai",
        query_field="text",
    ),
    ("openai", "summarize_text"): IntentSpec(
        intent="assistant.summarize",
        required_fields=("text",),
        provider="openai",
        query_field="text",
    ),
    ("openai", "outline"): IntentSpec(
        intent="assistant.outline",
        required_fields=("topic",),
        provider="openai",
        query_field="topic",
    ),
}


def _decision_for(final_conf: float) -> str:
    if final_conf >= 0.80:
        return "execute"
    if final_conf >= 0.55:
        return "soft_confirm"
    if final_conf >= 0.35:
        return "clarify"
    return "block"


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _is_field_present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _has_meaningful_input(args: Dict[str, object]) -> bool:
    return any(_is_field_present(value) for value in args.values())


def _extract_text_field(args: Dict[str, object], field: Optional[str]) -> Optional[str]:
    if not field:
        return None
    value = args.get(field)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
