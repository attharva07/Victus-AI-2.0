from __future__ import annotations

import json
from typing import Callable, Dict, List, Optional

import requests

from ....config.runtime import get_ollama_base_url, get_ollama_model
from ....core.llm_health import get_llm_request_timeout
from ....core.schemas import ExecutionError
from .llm_base import LLMClientBase


class OllamaClient(LLMClientBase):
    """LLM client powered by a local Ollama server."""

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = (base_url or get_ollama_base_url()).rstrip("/")
        self.model = model or get_ollama_model()

    def _stream_prompt(
        self,
        prompt: str,
        *,
        on_chunk: Optional[Callable[[str], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {"model": self.model, "prompt": prompt, "stream": True}
        chunks: list[str] = []
        callback = on_chunk or (lambda chunk: None)
        try:
            timeout = get_llm_request_timeout()
            response = requests.post(
                url,
                json=payload,
                stream=True,
                timeout=(timeout, timeout),
            )
        except requests.RequestException as exc:  # pragma: no cover - network dependency
            raise ExecutionError(f"Ollama request failed: {exc}") from exc

        if response.status_code != 200:
            raise ExecutionError(
                f"Ollama request failed with status {response.status_code}: {response.text}"
            )

        try:
            for line in response.iter_lines(decode_unicode=True):
                if should_stop and should_stop():
                    response.close()
                    break
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except ValueError:
                    continue
                chunk = data.get("response", "") if isinstance(data, dict) else ""
                if chunk:
                    chunks.append(chunk)
                    callback(chunk)
        except requests.RequestException as exc:  # pragma: no cover - network dependency
            raise ExecutionError(f"Streaming from Ollama failed: {exc}") from exc
        finally:
            response.close()

        return "".join(chunks)

    def _post_prompt(self, prompt: str) -> str:
        return self._stream_prompt(prompt)

    def generate_text(self, *, prompt: str) -> Dict[str, str]:
        content = self._post_prompt(prompt)
        return {"action": "generate_text", "content": content}

    def stream_generate_text(
        self,
        *,
        prompt: str,
        on_chunk: Optional[Callable[[str], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> str:
        return self._stream_prompt(prompt, on_chunk=on_chunk, should_stop=should_stop)

    def summarize(self, *, text: str) -> Dict[str, str]:
        summary = self._post_prompt(text)
        return {"action": "summarize", "summary": summary}

    def outline(self, *, topic: str) -> Dict[str, List[str]]:
        outline_text = self._post_prompt(topic)
        outline_items = [line.strip("- ") for line in outline_text.splitlines() if line.strip()]
        return {"action": "outline", "outline": outline_items}

    def draft_email(self, *, to: str, subject: str, body: str) -> Dict[str, str]:
        prompt = f"To: {to}\nSubject: {subject}\nBody: {body}"
        draft_body = self._post_prompt(prompt)
        return {"action": "draft_email", "to": to, "subject": subject, "body": draft_body}
