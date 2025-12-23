# Victus AI 2.0

## Project Overview
Victus is a policy-first orchestration engine: planners propose actions, policy reviews them, and executors only act on approved steps under strict guardrails.

## Core Logic Pipeline
- Input → Plan → Policy → Approval → Execute → Audit
- Nothing executes without policy approval and matching constraints.

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
