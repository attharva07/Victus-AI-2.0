from __future__ import annotations

from adapters.llm.provider import LLMProvider
from core.filesystem.service import list_sandbox_files, read_sandbox_file, write_sandbox_file
from core.finance.service import add_transaction, list_transactions, summary
from core.logging.audit import audit_event
from core.memory.service import add_memory, delete_memory, list_recent, search_memories
from core.orchestrator.deterministic import looks_like_finance, parse_intent
from core.orchestrator.policy import validate_intent
from core.orchestrator.schemas import ActionResult, Intent, OrchestrateRequest, OrchestrateResponse


def _deterministic_route(request: OrchestrateRequest) -> Intent | None:
    return parse_intent(request.utterance)


def _execute_intent(intent: Intent) -> tuple[str, list[ActionResult]]:
    action = intent.action
    params = intent.parameters
    if action == "memory.add":
        memory_id = add_memory(content=params["content"])
        audit_event("orchestrate_memory_add", memory_id=memory_id)
        result = ActionResult(action=action, parameters=params, result={"id": memory_id})
        return f"Saved memory {memory_id}.", [result]
    if action == "memory.search":
        results = search_memories(query=params.get("query", ""), tags=params.get("tags"), limit=params.get("limit", 10))
        audit_event("orchestrate_memory_search", query=params.get("query", ""))
        result = ActionResult(action=action, parameters=params, result={"results": results})
        return f"Found {len(results)} memories.", [result]
    if action == "memory.list":
        results = list_recent(limit=params.get("limit", 20))
        audit_event("orchestrate_memory_list", limit=params.get("limit", 20))
        result = ActionResult(action=action, parameters=params, result={"results": results})
        return f"Listed {len(results)} memories.", [result]
    if action == "memory.delete":
        deleted = delete_memory(memory_id=params["id"])
        audit_event("orchestrate_memory_delete", memory_id=params["id"], deleted=deleted)
        result = ActionResult(action=action, parameters=params, result={"deleted": deleted})
        return ("Memory deleted." if deleted else "Memory not found."), [result]
    if action == "finance.add_transaction":
        amount = params["amount"]
        amount_cents = int(round(float(amount) * 100))
        transaction_id = add_transaction(
            amount_cents=amount_cents,
            category=params.get("category", "uncategorized"),
            merchant=params.get("merchant"),
        )
        audit_event("orchestrate_finance_add", transaction_id=transaction_id)
        result = ActionResult(
            action=action,
            parameters=params,
            result={"id": transaction_id, "amount_cents": amount_cents},
        )
        return f"Recorded transaction {transaction_id}.", [result]
    if action == "finance.list_transactions":
        results = list_transactions(limit=params.get("limit", 50), category=params.get("category"))
        audit_event("orchestrate_finance_list", count=len(results))
        result = ActionResult(action=action, parameters=params, result={"results": results})
        return f"Listed {len(results)} transactions.", [result]
    if action == "finance.summary":
        report = summary(period=params.get("period", "week"), group_by=params.get("group_by", "category"))
        audit_event("orchestrate_finance_summary", period=report["period"])
        result = ActionResult(action=action, parameters=params, result={"report": report})
        return "Generated finance summary.", [result]
    if action == "files.list":
        files = list_sandbox_files()
        result = ActionResult(action=action, parameters=params, result={"files": files})
        return f"Listed {len(files)} files.", [result]
    if action == "files.read":
        content = read_sandbox_file(params["path"])
        result = ActionResult(action=action, parameters=params, result={"content": content})
        return f"Read file {params['path']}.", [result]
    if action == "files.write":
        write_sandbox_file(params["path"], params.get("content", ""), params.get("mode", "overwrite"))
        result = ActionResult(action=action, parameters=params, result={"ok": True})
        return f"Wrote file {params['path']}.", [result]
    return "No action executed.", []


def route_intent(request: OrchestrateRequest, llm_provider: LLMProvider) -> OrchestrateResponse:
    intent = _deterministic_route(request)
    if intent is None:
        proposed = llm_provider.propose_intent(request)
        if proposed is None or proposed.confidence < 0.7:
            intent = Intent(action="noop", parameters={}, confidence=0.0)
            message = "Phase 1 scaffold: no actions executed."
            if looks_like_finance(request.utterance):
                message = "I need more detail to record that transaction."
            return OrchestrateResponse(intent=intent, message=message, actions=[])
        intent = proposed
    intent = validate_intent(intent)
    if intent.action == "noop":
        return OrchestrateResponse(
            intent=intent, message="Phase 1 scaffold: no actions executed.", actions=[]
        )
    message, actions = _execute_intent(intent)
    return OrchestrateResponse(intent=intent, message=message, actions=actions)
