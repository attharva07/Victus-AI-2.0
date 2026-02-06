# Phase 3.1 Layer 3: LLM proposer (deterministic-first)

## Decision

Layer 3 introduces an **LLM proposer fallback** that is invoked only when deterministic routing returns no intent.

Key constraints:

- Deterministic-first remains mandatory.
- LLM is proposer-only (cannot directly execute arbitrary actions).
- Proposed actions are validated by action allowlist + argument schema + policy gate.
- Auto-execution is disabled by default.

## Deterministic-first principle

1. Run deterministic parser/router.
2. If deterministic intent exists, execute as before.
3. If deterministic routing fails (`unknown_intent`) and proposer is enabled, request an LLM proposal.
4. Validate proposal. If invalid or disallowed, return `unknown_intent`.

## Proposer-only constraints

- Proposal output shape includes: `ok`, `confidence`, `action`, `args`, `reason`, `raw`.
- Proposal action must be in Layer 3 proposer allowlist.
- Arguments must pass pydantic schema checks before conversion into an orchestrator intent.
- Policy validation remains enforced.

## Auto-exec behavior

Default: proposal is returned, not executed.

Auto-exec is allowed only when all are true:

- `VICTUS_LLM_ALLOW_AUTOEXEC=true`
- `confidence >= VICTUS_LLM_AUTOEXEC_MIN_CONFIDENCE`
- Action is in safe autoexec allowlist (`memory.add`, `memory.search`)

## Environment variables

- `VICTUS_LLM_ENABLED` (default `false`)
- `VICTUS_LLM_PROVIDER` (default `stub`)
- `VICTUS_LLM_ALLOW_AUTOEXEC` (default `false`)
- `VICTUS_LLM_AUTOEXEC_MIN_CONFIDENCE` (default `0.90`)

Legacy compatibility:

- `VICTUS_ENABLE_LLM_FALLBACK=true` still enables fallback path.

## Response examples

### Deterministic success

```json
{
  "intent": {"action": "memory.add", "parameters": {"content": "x"}, "confidence": 1.0},
  "mode": "deterministic",
  "executed": true,
  "actions": [{"action": "memory.add", "result": {"id": "..."}}]
}
```

### LLM proposal (not auto-executed)

```json
{
  "intent": {"action": "memory.add", "parameters": {"content": "x"}, "confidence": 0.94},
  "mode": "llm_proposal",
  "proposed_action": {
    "action": "memory.add",
    "args": {"content": "x"},
    "confidence": 0.94,
    "reason": "inferred reminder"
  },
  "executed": false,
  "result": null,
  "actions": []
}
```

### Rejected proposal

```json
{
  "error": "unknown_intent",
  "message": "I could not deterministically map that request to a supported action."
}
```
