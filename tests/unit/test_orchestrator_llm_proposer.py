from __future__ import annotations

from pathlib import Path

import pytest

from adapters.llm.provider import LLMProposer, ProposalResult
from core.config import ensure_directories
from core.orchestrator.router import route_intent
from core.orchestrator.schemas import OrchestrateErrorResponse, OrchestrateRequest, OrchestrateResponse


class _NoopProposer(LLMProposer):
    def propose(self, text: str, domain: str | None, candidates: list[str], context: dict) -> ProposalResult:
        _ = (text, domain, candidates, context)
        return ProposalResult(ok=False, confidence=0.0, reason="none")


class _StaticProposer(LLMProposer):
    def __init__(self, result: ProposalResult):
        self._result = result

    def propose(self, text: str, domain: str | None, candidates: list[str], context: dict) -> ProposalResult:
        _ = (text, domain, candidates, context)
        return self._result


def test_deterministic_still_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VICTUS_LLM_ENABLED", "true")
    response = route_intent(OrchestrateRequest(text="list files"), _NoopProposer())
    assert isinstance(response, OrchestrateResponse)
    assert response.mode == "deterministic"
    assert response.intent.action == "files.list"


def test_unknown_intent_unchanged_when_llm_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VICTUS_LLM_ENABLED", raising=False)
    monkeypatch.delenv("VICTUS_ENABLE_LLM_FALLBACK", raising=False)
    response = route_intent(OrchestrateRequest(text="compute the moon phase please now"), _NoopProposer())
    assert isinstance(response, OrchestrateErrorResponse)
    assert response.error == "unknown_intent"


def test_llm_proposal_returned_not_executed_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VICTUS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VICTUS_LLM_ENABLED", "true")
    monkeypatch.setenv("VICTUS_LLM_ALLOW_AUTOEXEC", "false")
    ensure_directories()
    proposer = _StaticProposer(
        ProposalResult(
            ok=True,
            confidence=0.95,
            action="memory.add",
            args={"content": "buy oats"},
            reason="parsed user reminder",
        )
    )
    response = route_intent(OrchestrateRequest(text="please stash this detail"), proposer)
    assert response.mode == "llm_proposal"
    assert response.proposed_action is not None
    assert response.executed is False
    assert response.actions == []


def test_llm_autoexec_only_when_enabled_and_safe(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VICTUS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VICTUS_LLM_ENABLED", "true")
    monkeypatch.setenv("VICTUS_LLM_ALLOW_AUTOEXEC", "true")
    monkeypatch.setenv("VICTUS_LLM_AUTOEXEC_MIN_CONFIDENCE", "0.90")
    ensure_directories()

    proposer = _StaticProposer(
        ProposalResult(
            ok=True,
            confidence=0.96,
            action="memory.add",
            args={"content": "book dentist"},
            reason="clear memory add request",
        )
    )
    response = route_intent(OrchestrateRequest(text="capture this note"), proposer)
    assert response.mode == "llm_proposal"
    assert response.executed is True
    assert response.intent.action == "memory.add"
    assert response.actions


def test_disallowed_proposal_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VICTUS_LLM_ENABLED", "true")
    proposer = _StaticProposer(
        ProposalResult(
            ok=True,
            confidence=0.99,
            action="system.shell",
            args={"command": "rm -rf /"},
            reason="bad action",
        )
    )
    response = route_intent(OrchestrateRequest(text="do something dangerous now"), proposer)
    assert isinstance(response, OrchestrateErrorResponse)
    assert response.error == "unknown_intent"
