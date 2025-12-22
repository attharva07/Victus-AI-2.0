# Victus AI 2.0

Victus AI is a local, security-first orchestration system that plans, validates, and executes user-intended actions under strict policy control. It is **not** an autonomous agent or a generic chatbot; intelligence only proposes, while policy decides and execution obeys.

## Project Overview and Philosophy
- **Security first:** Every input (including LLM output) is untrusted and must pass policy validation before anything executes.
- **Least privilege:** Only narrow, allowlisted capabilities exist; unknown or denylisted actions are rejected by default.
- **Auditability:** Each request records inputs, plans, approvals, execution results, and errors with secret redaction.
- **Deterministic interfaces:** All planners, policy engines, and plugins follow strict schemas to remove ambiguity.

## Privilege Pyramid Summary
1. **Rules & Policies (Supreme Authority):** Define allow/deny decisions, confirmation, data boundaries, and audit requirements.
2. **Router + Planner (Untrusted Brain):** Parses input and outputs a structured JSON plan; cannot execute.
3. **Tool Plugins (Untrusted Hands):** Domain-specific actions (system, Spotify, Gmail, OpenAI, Docs) with narrow allowlists.
4. **Execution Engine:** Runs only policy-approved steps and refuses to operate without a signed approval token.

## Execution Flow (Textual Diagram)
```
Input (text/voice)
  → Plan (router/planner emits strict Plan schema)
  → Policy Check (validates tools/actions, risk, data boundaries)
  → Approval Token Issued (policy signature + constraints)
  → Execute (executors run only approved steps)
  → Audit (log input, plan, approvals, results, errors)
```
Failure at any stage stops the flow and returns a safe error.

## Phase 1 Status
- Baseline policy gate, executor, schemas, and audit logger are implemented and covered by unit flow tests.
- `victus/app.py` wires Router → Planner → Policy → Executor → Audit so interfaces can call a single entry point (`VictusApp.run_request`).

## Phase 2 Kickoff
- Phase 1 scaffolding is complete; phase 2 focuses on hardening and filling the stubs into working components.
- Goals for this phase include:
  - Implementing full planner, policy, and executor logic beyond placeholders.
  - Replacing plugin stubs with validated, allowlisted capabilities per domain.
  - Completing interface layers (UI/voice/hotkey) while preserving policy-first execution.
  - Expanding tests to cover integration, security, and regression cases for the new behaviors.
  - Updating documentation alongside any behavior change to keep policy guardrails explicit.
- Development status updates:
  - Policy now enforces domain segmentation: system-only plans cannot call productivity tools and vice versa unless the plan is explicitly `mixed`.
  - Phase 2 checklists in `docs/DEV_GUIDE.md` and `CONTRIBUTING.md` are actively maintained to reflect completed validations and tests.


## Safety Invariants (Non-Negotiable)
- No admin/debug bypasses, hidden overrides, or generic shell execution.
- Plugins never execute without a valid `policy_signature`.
- System domain enforces hard boundaries: no raw shell, firewall/port manipulation, kernel/driver access, or credential dumping.
- OpenAI is used only for reasoning/classification/drafting; it never receives secrets or raw logs and cannot execute actions.
- Screenshots happen only when explicitly requested by a plan step and are never stored without permission.

## High-Level Module Layout
While implementation is in-progress, the architecture is fixed and reflected in the codebase:
- **Planner/Router:** Parses user input (text/voice) and emits a Plan object (schema defined in `victus/schemas.py`).
- **Policy Engine (`victus/policy.py`):** Validates schema, allowlists/denylists, risk, confirmation, and data boundaries; returns Approval objects.
- **Execution Engine (`victus/executor.py`):** Enforces approvals and constraints, dispatching only approved steps to plugins and refusing to run without a signed policy signature.
- **Plugins (`victus/plugins/base.py`):** Implement `capabilities`, `validate_args`, and `execute` for allowlisted actions in domains such as `system`, `spotify`, `gmail`, `openai`, and `docs`.
- **Audit Logger (`victus/audit.py`):** Records input, plan, approval, executed steps, and results with secret redaction.

While implementation is in-progress, the architecture is fixed:
- **Planner/Router:** Parses user input (text/voice) and emits a Plan object.
- **Policy Engine:** Validates schema, allowlists/denylists, risk, confirmation, and data boundaries; returns Approval objects.
- **Execution Engine:** Enforces approvals and constraints, dispatching only approved steps to plugins.
- **Plugins:** Implement `capabilities`, `validate_args`, and `execute` for allowlisted actions in domains such as `system`, `spotify`, `gmail`, `openai`, and `docs`.
- **Audit Logger:** Records input, plan, approval, executed steps, and results with secret redaction.

- **Configs:** Dev/prod policy files (e.g., `policy_dev.yaml`, `policy_prod.yaml`) that never bypass enforcement.

## Policies: Dev vs Prod
- Both environments enforce policy; dev may be more permissive but cannot disable validation or auditing.
- Unknown tools/actions, denylisted entries, or non-allowlisted system commands are denied in all modes.
- Medium/high-risk plans or sensitive actions (e.g., `gmail.send`) require confirmation regardless of environment.

## How to Run Tests
All automated tests must run via a single command:
```bash
pytest
```
Tests will cover policy allow/deny logic, plan schema validation, plugin argument validation, end-to-end flows, security cases (prompt injection, execution without approvals), and regression coverage for fixed bugs.

## Adding a New Plugin Safely
1. **Define capabilities:** Implement `capabilities()` with explicit actions and argument schemas; deny by default.
2. **Validate inputs:** Implement `validate_args(action, args)` to enforce schemas and reject unknown actions.
3. **Guard execution:** `execute(action, args, context, approval)` must refuse to run without a valid approval token and must honor constraints (time limits, redaction, no screenshot storage).
4. **Respect domains:** Plugins must not escalate privilege or call other plugins; system plugins may only expose allowlisted operations.
5. **Update policies:** Add allowlist entries to the appropriate policy file; unknown actions remain denied.
6. **Document and test:** Add README notes if behavior changes, and create unit/integration tests to cover capabilities, validation, and denial cases.

## Execution Flow Diagram (Concise)
- Input → Plan → Policy → Approval → Execute → Audit
- Any failure halts execution; system fails closed.

## Documentation
- Developer workflow, schemas, and guardrails: [`docs/DEV_GUIDE.md`](docs/DEV_GUIDE.md)
- Contribution rules and review checklist: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Policy invariants and gate rules: [`docs/POLICY.md`](docs/POLICY.md)
