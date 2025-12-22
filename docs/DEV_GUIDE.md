# Victus AI 2.0 Developer Guide

This guide is the authoritative operating manual for Codex development. Follow it for every change to ensure security, policy compliance, and consistent workflows.

## Execution Flow (must remain intact)
1. **Input ingestion** (text/voice) is untrusted.
2. **Planner/Router** parses input and emits a structured Plan that follows the Plan schema.
3. **Policy Engine** validates the plan, applies allow/deny lists, checks privacy, and issues an Approval token.
4. **Executor** refuses to run without a valid Approval signature and only dispatches approved steps to plugins.
5. **Audit Logger** records input, plan, approvals, results, errors, and redactions.

## Schemas Summary
- **Context**: Includes session metadata, mode (`dev` or `prod`), foreground app, user confirmation flag, and privacy settings (screenshot, OpenAI, storage).
- **Plan**: Goal, domain (`system`/`productivity`/`mixed`), ordered PlanSteps, risk level, confirmation requirement, outbound data settings, and notes.
- **PlanStep**: `id`, `tool`, `action`, `args`, input/output characteristics (e.g., screenshot usage, side effects).
- **Approval**: Approval flag, approved step IDs, confirmation requirement, constraints (time limit, screenshot storage, redaction), and `policy_signature`.
- **Errors**: `PolicyError` for violations; `ExecutionError` for missing approvals or unregistered plugins.

## How to Run Tests
All automated coverage must be runnable via a single command:
```bash
pytest
```
Run it locally before opening a PR.

## Adding a Plugin Safely
1. **Define capabilities** explicitly (`capabilities()`), deny everything else by default.
2. **Validate inputs** in `validate_args`; reject unknown actions or malformed arguments.
3. **Guard execution** in `execute`; refuse to run without a valid approval token and honor constraints (e.g., no screenshot storage, redaction before OpenAI).
4. **Respect domains**: system plugins stay narrow (no raw shell, no privilege escalation); productivity plugins cannot execute system-level actions.
5. **Update policy config** with allowlist entries; unknown actions remain denied.
6. **Document and test** new capabilities with unit, integration, and security coverage.

## Codex Checklist (must tick for every task)
Phase 1 baseline has been verified; checkboxes are marked to reflect the current repository state. Future changes must keep these items true.
### Scope + Safety
- [x] Restate scope: what changes and what does not
- [x] Confirm policy supremacy is unchanged
- [x] Confirm segmentation (System vs Productivity) is preserved
- [x] Confirm no raw shell / no generic exec wrappers were added

### Schemas + Interfaces
- [x] Planner outputs Plan Schema exactly
- [x] Policy outputs Approval Schema exactly
- [x] Context Schema respected (privacy flags)
- [x] Plugins implement required interface
- [x] Plugin execution requires valid approval token/signature

### Logging + Privacy
- [x] Audit logs generated for each request
- [x] Secrets redacted (no tokens/passwords)
- [x] Screenshot capture is explicit-only and logged

### Testing + Quality
- [x] Unit tests updated/added
- [x] Integration tests updated/added
- [x] Security tests included for edge cases
- [x] Regression test added for any bug fix

### Documentation
- [x] README updated if behavior changed
- [x] DEV_GUIDE / CONTRIBUTING updated if workflow changed

### Scope + Safety
- [ ] Restate scope: what changes and what does not
- [ ] Confirm policy supremacy is unchanged
- [ ] Confirm segmentation (System vs Productivity) is preserved
- [ ] Confirm no raw shell / no generic exec wrappers were added

### Schemas + Interfaces
- [ ] Planner outputs Plan Schema exactly
- [ ] Policy outputs Approval Schema exactly
- [ ] Context Schema respected (privacy flags)
- [ ] Plugins implement required interface
- [ ] Plugin execution requires valid approval token/signature

### Logging + Privacy
- [ ] Audit logs generated for each request
- [ ] Secrets redacted (no tokens/passwords)
- [ ] Screenshot capture is explicit-only and logged

### Testing + Quality
- [ ] Unit tests updated/added
- [ ] Integration tests updated/added
- [ ] Security tests included for edge cases
- [ ] Regression test added for any bug fix

### Documentation
- [ ] README updated if behavior changed
- [ ] DEV_GUIDE / CONTRIBUTING updated if workflow changed

## Codex Task Template
Copy/paste and fill this template for every task:

```
**Objective:** <one sentence>

**Constraints (must obey):**
* No tool runs without policy approval
* No raw shell / cmd / powershell / bash generic exec
* System and Productivity domains remain separated
* LLM output is untrusted; policy decides
* Respect Plan/Approval/Context schemas

**Required deliverables:**
* Code changes
* Tests (unit + integration + security where applicable)
* Documentation updates (README/DEV_GUIDE/CONTRIBUTING if needed)

**Definition of Done:**
* All tests pass via `pytest`
* Checklist Completed section filled with file references
```

## Non-Negotiable Invariants and Guardrails
- No admin/debug bypasses or temporary overrides.
- Never add generic shell execution (`subprocess.run(command_string)` or similar).
- Plugins never execute without a valid `policy_signature`.
- System domain boundaries: no firewall/port manipulation, kernel access, credential dumping, or raw shelling.
- OpenAI is used only for reasoning/classification/drafting; never send secrets or raw logs.
- Screenshots happen only when a plan explicitly requests them; never store without consent.

## Release and Review Expectations
- Policy gate must remain the first line of defense; executor must always require approval.
- Any behavior change must update at least one of: `README.md`, `docs/DEV_GUIDE.md`, `CONTRIBUTING.md`, or `docs/POLICY.md`.
- Pull requests should demonstrate updated tests and documentation reflecting the change.
