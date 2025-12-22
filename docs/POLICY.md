# Victus AI 2.0 Policy Invariants

These non-negotiable rules govern all behavior and must never be bypassed.

## Supreme Policy Gate
- Planner output is untrusted. Policy must validate every plan and issue an approval token before execution.
- Executor refuses to run without a valid approval and policy signature.

## Guardrails
- No admin/debug bypasses or temporary overrides.
- No generic shell execution (`subprocess.run` with arbitrary commands) or privilege escalation.
- System domain boundaries: no firewall/port manipulation, kernel/driver access, credential dumping, or raw shelling.
- Plugins never execute without `policy_signature` and must validate inputs.
- OpenAI usage is limited to reasoning/classification/drafting; never send secrets or raw audit logs.
- Screenshots only on explicit plan request; never store images without consent.

## Domain Segmentation
- **System**: Narrow, allowlisted actions only; cannot be triggered from productivity plugins.
- **Productivity**: Text-first capabilities (e.g., OpenAI drafting, doc generation) without system-level side effects unless policy allows.

## Privacy and Logging
- Audit logging required for every request; include input, plan, approval, results, and errors.
- Secrets must be redacted before logging or outbound transfers.
- Screenshot capture must be explicit, consented, and logged; storage defaults to off unless approval allows.

## Change Management
- Any behavior change must update at least one repo doc (`README.md`, `docs/DEV_GUIDE.md`, `CONTRIBUTING.md`, or this file).
- Tests (unit, integration, security, regression) must accompany functional changes.
