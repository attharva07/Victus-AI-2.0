from __future__ import annotations

import os
from typing import Dict, List

from openai import OpenAI

from ....core.schemas import ExecutionError


class OpenAIClientReal:
    """Real OpenAI client that mirrors the stub output format."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ExecutionError("OPENAI_API_KEY is required to use the OpenAI client.")

        self.client = OpenAI(api_key=self.api_key)

    def _chat_completion(self, messages) -> str:
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
            )
        except Exception as exc:  # pragma: no cover - network dependency
            raise ExecutionError(f"OpenAI request failed: {exc}") from exc

        if not response.choices:
            return ""

        return response.choices[0].message.content or ""

    def generate_text(self, *, prompt: str) -> Dict[str, str]:
        content = self._chat_completion(
            [
                {"role": "system", "content": "You generate helpful productivity text."},
                {"role": "user", "content": prompt},
            ]
        )
        return {"action": "generate_text", "content": content}

    def summarize(self, *, text: str) -> Dict[str, str]:
        summary = self._chat_completion(
            [
                {"role": "system", "content": "Provide a concise summary of the user's text."},
                {"role": "user", "content": text},
            ]
        )
        return {"action": "summarize", "summary": summary}

    def outline(self, *, topic: str) -> Dict[str, List[str]]:
        outline_text = self._chat_completion(
            [
                {
                    "role": "system",
                    "content": "Create a short outline as a bullet list. Return one bullet per line.",
                },
                {"role": "user", "content": topic},
            ]
        )
        outline_items = [line.strip("- ") for line in outline_text.splitlines() if line.strip()]
        return {"action": "outline", "outline": outline_items}

    def draft_email(self, *, to: str, subject: str, body: str) -> Dict[str, str]:
        draft_body = self._chat_completion(
            [
                {
                    "role": "system",
                    "content": "Draft a clear and concise email using the provided details.",
                },
                {
                    "role": "user",
                    "content": f"To: {to}\nSubject: {subject}\nBody: {body}",
                },
            ]
        )
        return {"action": "draft_email", "to": to, "subject": subject, "body": draft_body}
