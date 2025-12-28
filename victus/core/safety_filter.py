from __future__ import annotations

import re
from typing import Iterable


class SafetyFilter:
    """Detect suspicious control or execution tokens in user input."""

    def __init__(self, *, suspicious_tokens: Iterable[str] | None = None) -> None:
        default_tokens = [
            "cmd",
            "powershell",
            "bash",
            "sudo",
            "rm -rf",
            "del ",
            "format ",
            "reg ",
            "invoke-",
            "iex",
            "nmap",
            "nc",
            "tcpdump",
            "wireshark",
        ]
        self.suspicious_tokens = tuple(token.lower() for token in (suspicious_tokens or default_tokens))
        self._code_fence = re.compile(r"```", re.MULTILINE)
        self._base64_blob = re.compile(r"[A-Za-z0-9+/]{32,}={0,2}")

    def is_suspicious(self, user_input: str) -> bool:
        normalized = user_input.lower()
        if self._code_fence.search(user_input):
            return True
        if self._base64_blob.search(user_input):
            return True
        return any(token in normalized for token in self.suspicious_tokens)
