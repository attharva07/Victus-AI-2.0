from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from typing import Optional

from victus.app import VictusApp
from victus.core.intent_router import route_intent
from victus.core.schemas import Context, IntentPlan, Plan, PlanStep, PrivacySettings
from victus.core.safety_filter import SafetyFilter
from victus.domains.productivity.allowlisted_plugins import (
    DocsPlugin,
    GmailPlugin,
    OpenAIPlugin,
    SpotifyPlugin,
)
from victus.domains.productivity.plugins.llm_base import LLMClientBase
from victus.domains.system.system_plugin import SystemPlugin

from .local_plugin import LocalTaskPlugin


_YOUTUBE_URL_RE = re.compile(r"https?://\\S+")


def _build_context() -> Context:
    return Context(
        session_id="victus-local-ui",
        timestamp=datetime.utcnow(),
        mode="dev",
        foreground_app=None,
        privacy=PrivacySettings(allow_send_to_openai=True),
    )


def _local_rule_router(user_text: str, _context: Context) -> Plan | None:
    normalized = user_text.strip()
    lower = normalized.lower()
    if "youtube" in lower:
        url_match = _YOUTUBE_URL_RE.search(normalized)
        if url_match:
            return Plan(
                goal=user_text,
                domain="productivity",
                steps=[
                    PlanStep(
                        id="step-1",
                        tool="local",
                        action="open_youtube",
                        args={"url": url_match.group(0)},
                    )
                ],
                risk="low",
                origin="router",
            )
        query = re.sub(r"(open|play|search|youtube|for)+", "", lower).strip()
        if query:
            return Plan(
                goal=user_text,
                domain="productivity",
                steps=[
                    PlanStep(
                        id="step-1",
                        tool="local",
                        action="open_youtube",
                        args={"query": query},
                    )
                ],
                risk="low",
                origin="router",
            )

    if lower.startswith(("open ", "launch ")):
        app_name = normalized.split(" ", 1)[1].strip()
        if app_name:
            return Plan(
                goal=user_text,
                domain="productivity",
                steps=[
                    PlanStep(
                        id="step-1",
                        tool="local",
                        action="open_app",
                        args={"name": app_name},
                    )
                ],
                risk="low",
                origin="router",
            )

    routed_action = route_intent(user_text, safety_filter=SafetyFilter())
    if routed_action:
        return Plan(
            goal=user_text,
            domain="system",
            steps=[
                PlanStep(
                    id="step-1",
                    tool="system",
                    action=routed_action.action,
                    args=routed_action.args,
                )
            ],
            risk="low",
            origin="router",
        )

    return None


class LocalIntentPlanner:
    def __init__(self, client: LLMClientBase) -> None:
        self.client = client

    async def __call__(self, user_text: str, _context: Context) -> Optional[IntentPlan]:
        prompt = (
            "You are an intent planner for a local desktop assistant. "
            "Decide if the user wants a tool action or a chat response. "
            "Allowed tools: open_app (args: name or path), open_youtube (args: query or url). "
            "If you need clarification, ask for it. "
            "Respond with strict JSON only: "
            "{\"intent\":\"chat|tool|clarify\",\"tool\":null|\"open_app\"|\"open_youtube\","
            "\"args\":{},\"clarification\":null|\"...\"}.\n"
            f"User: {user_text}"
        )
        try:
            response = await asyncio.to_thread(self.client.generate_text, prompt=prompt)
        except Exception:
            return None
        content = response.get("content", "") if isinstance(response, dict) else ""
        data = _safe_json_extract(content)
        if not data:
            return None
        intent = data.get("intent")
        if intent == "tool":
            tool = data.get("tool")
            if tool == "open_app":
                return IntentPlan(kind="tool", tool="local", action="open_app", args=data.get("args", {}))
            if tool == "open_youtube":
                return IntentPlan(kind="tool", tool="local", action="open_youtube", args=data.get("args", {}))
        if intent == "clarify":
            return IntentPlan(kind="clarify", message=data.get("clarification"))
        if intent == "chat":
            return IntentPlan(kind="chat")
        return None


def _safe_json_extract(text: str) -> Optional[dict]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"{.*}", text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def build_victus_app() -> VictusApp:
    plugins = {
        "system": SystemPlugin(),
        "gmail": GmailPlugin(),
        "docs": DocsPlugin(),
        "spotify": SpotifyPlugin(),
        "openai": OpenAIPlugin(),
        "local": LocalTaskPlugin(),
    }
    llm_client = plugins["openai"].client
    return VictusApp(
        plugins,
        context_factory=_build_context,
        rule_router=_local_rule_router,
        intent_planner=LocalIntentPlanner(llm_client),
    )
