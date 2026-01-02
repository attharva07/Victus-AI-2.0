# Victus AI 2.0

## Project Overview
Victus is a policy-first orchestration engine: planners propose actions, policy reviews them, and executors only act on approved steps under strict guardrails.

## Core Logic Pipeline
- Input → Plan → Policy → Approval → Execute → Audit
- Nothing executes without policy approval and matching constraints.

## Stage 1 — Policy-First Foundations
Victus Stage 1 tracks every shipped phase of the policy-first assistant. Each phase builds on the same safeguarded pipeline and retains strict approval gating.

- **Phase 1: Baseline orchestration (complete)** — Establishes the end-to-end flow from routing/planning through policy approval, guarded execution, and audit logging. System-only plans execute only when policy issues a signed approval token, and every request lands in the audit log.
- **Phase 2: Hardened mixed domains (complete)** — Adds mixed-domain support and stronger policy checks: domain-aware allow/deny lists, privacy enforcement, confirmation for sensitive actions, plugin argument validation, and executor signature verification for approved step IDs.
- **Phase 3: Privacy-gated productivity (complete)** — Introduces OpenAI-backed text transformations (generate, draft email, summarize, outline) behind explicit privacy opt-ins. Prompts are redacted before outbound calls, audit logs redact sensitive text, and productivity actions remain blocked from system domains.
- **Phase 4: Popup desktop demo (complete)** — Delivers a text-only Qt popup that routes user text through `VictusApp.run_request`, with Ready/Thinking/Denied/Error status pills and transcript rendering. The UI now renders correctly (logic issues with showing system entries are nearly resolved), skips tray icons/hotkeys, assumes local desktop use, and keeps policy/executor in the loop.

## Quick Demo (60 seconds)
Run the full suite:
```bash
pytest -q
```
Passing tests prove policy enforcement, execution gating, and audit logging (for example, mixed-domain flows and approval validation).

## Safety Guarantees
- No execution without approval
- No raw shell execution
- Domain separation enforced
- Full audit logging

## Documentation Links
- [docs/DEV_GUIDE.md](docs/DEV_GUIDE.md)
- [docs/POLICY.md](docs/POLICY.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
