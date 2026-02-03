# Phase 0 CI Green Gate (Cleanup + Workflow Hygiene)

## What was failing
- CI quality job installs only `requirements.txt`, but runs Ruff, pytest, and coverage without their dependencies.
- `scripts/quality_report.py` imported `victus` modules before injecting the repo root into `sys.path`, which violates the existing import-order test.
- No Cloudflare Workers workflow was found in `.github/workflows/`, so there was nothing to path-filter for worker builds.

## What changed
- Added `requirements-dev.txt` with Ruff, pytest, and pytest-cov, and updated CI to install it.
- Fixed `scripts/quality_report.py` import order so repo root is injected before `victus` imports.
- Added `victus_local/__init__.py` to make the local package explicit for imports.
- Documented the absence of a Workers workflow so it can be added later without guessing.

## How to run locally (mirrors CI)
```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
ruff check .
pytest -q --disable-warnings
pytest --cov=victus --cov-report=term-missing --cov-report=xml
python scripts/quality_report.py
```

## Workers build path-filter note
No Cloudflare Workers workflow exists in `.github/workflows/` today, so no path filters could be applied yet. Add path filters when a Workers workflow is introduced.
