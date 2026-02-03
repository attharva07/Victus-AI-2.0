from __future__ import annotations

import re
from typing import Optional

from core.orchestrator.schemas import Intent


def _normalize(text: str) -> str:
    return " ".join(text.strip().split())


def parse_memory_intent(utterance: str) -> Optional[Intent]:
    lowered = utterance.lower().strip()
    if lowered.startswith("remember "):
        content = _normalize(utterance[len("remember ") :])
        if content:
            return Intent(action="memory.add", parameters={"content": content}, confidence=1.0)
    if lowered.startswith("save "):
        content = _normalize(utterance[len("save ") :])
        if content:
            return Intent(action="memory.add", parameters={"content": content}, confidence=1.0)
    if lowered.startswith("what do you remember about "):
        query = _normalize(utterance[len("what do you remember about ") :])
        if query:
            return Intent(action="memory.search", parameters={"query": query}, confidence=1.0)
    if lowered.startswith("recall "):
        query = _normalize(utterance[len("recall ") :])
        if query:
            return Intent(action="memory.search", parameters={"query": query}, confidence=1.0)
    if lowered in {"list memories", "show memories"}:
        return Intent(action="memory.list", parameters={}, confidence=1.0)
    if lowered.startswith("forget "):
        memory_id = _normalize(utterance[len("forget ") :])
        if memory_id:
            return Intent(action="memory.delete", parameters={"id": memory_id}, confidence=1.0)
    return None


def _extract_amount(text: str) -> Optional[float]:
    match = re.search(r"\$?(\d+(?:\.\d{1,2})?)", text)
    if not match:
        return None
    return float(match.group(1))


def _parse_category_and_merchant(text: str) -> tuple[str | None, str | None]:
    lowered = text.strip()
    if " at " in lowered:
        category_part, merchant_part = lowered.split(" at ", 1)
        return category_part.strip(), merchant_part.strip()
    return lowered.strip(), None


def parse_finance_intent(utterance: str) -> Optional[Intent]:
    lowered = utterance.lower()
    spent_paid = re.search(r"\b(spent|paid)\b", lowered)
    if spent_paid:
        amount = _extract_amount(lowered)
        if amount is None:
            return None
        match = re.search(r"\b(spent|paid)\b.*?\$?\d+(?:\.\d{1,2})?\s*(?:dollars|bucks)?\s*(?:on|for)\s+(.+)", lowered)
        if not match:
            return None
        category_raw = match.group(2)
        category, merchant = _parse_category_and_merchant(category_raw)
        if not category:
            return None
        return Intent(
            action="finance.add_transaction",
            parameters={"amount": amount, "category": category, "merchant": merchant},
            confidence=1.0,
        )
    if "bought " in lowered and " for " in lowered:
        match = re.search(r"\bbought\s+(.+?)\s+for\s+\$?(\d+(?:\.\d{1,2})?)", lowered)
        if not match:
            return None
        category_raw = match.group(1)
        amount = float(match.group(2))
        category, merchant = _parse_category_and_merchant(category_raw)
        if not category:
            return None
        return Intent(
            action="finance.add_transaction",
            parameters={"amount": amount, "category": category, "merchant": merchant},
            confidence=1.0,
        )
    if lowered in {"list transactions", "show transactions"}:
        return Intent(action="finance.list_transactions", parameters={}, confidence=1.0)
    if ("summary" in lowered and "transaction" in lowered) or "spending summary" in lowered:
        period = "week"
        if "month" in lowered:
            period = "month"
        if "week" in lowered:
            period = "week"
        return Intent(action="finance.summary", parameters={"period": period}, confidence=1.0)
    if lowered in {"finance summary", "summary"}:
        return Intent(action="finance.summary", parameters={"period": "week"}, confidence=1.0)
    return None


def parse_files_intent(utterance: str) -> Optional[Intent]:
    lowered = utterance.lower().strip()
    if lowered == "list files":
        return Intent(action="files.list", parameters={}, confidence=1.0)
    if lowered.startswith("read file "):
        path = _normalize(utterance[len("read file ") :])
        if path:
            return Intent(action="files.read", parameters={"path": path}, confidence=1.0)
    if lowered.startswith("append to "):
        payload = utterance[len("append to ") :]
        if ":" in payload:
            path, content = payload.split(":", 1)
            path = _normalize(path)
            if path:
                return Intent(
                    action="files.write",
                    parameters={"path": path, "content": content.lstrip(), "mode": "append"},
                    confidence=1.0,
                )
    if lowered.startswith("write to "):
        payload = utterance[len("write to ") :]
        if ":" in payload:
            path, content = payload.split(":", 1)
            path = _normalize(path)
            if path:
                return Intent(
                    action="files.write",
                    parameters={"path": path, "content": content.lstrip(), "mode": "overwrite"},
                    confidence=1.0,
                )
    return None


def parse_camera_intent(utterance: str) -> Optional[Intent]:
    lowered = utterance.lower().strip()
    if lowered in {"camera status", "status camera", "camera state"}:
        return Intent(action="camera.status", parameters={}, confidence=1.0)
    if lowered in {"capture photo", "take a picture", "take a photo"}:
        return Intent(action="camera.capture", parameters={}, confidence=1.0)
    if lowered in {"detect face", "detect faces", "recognize", "recognize faces"}:
        return Intent(action="camera.recognize", parameters={}, confidence=1.0)
    return None


def parse_intent(utterance: str) -> Optional[Intent]:
    return (
        parse_camera_intent(utterance)
        or parse_memory_intent(utterance)
        or parse_finance_intent(utterance)
        or parse_files_intent(utterance)
    )


def looks_like_finance(utterance: str) -> bool:
    lowered = utterance.lower()
    return any(keyword in lowered for keyword in ("spent", "paid", "bought"))
