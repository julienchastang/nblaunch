# Title
Stage 02 - Service scaffold and bootstrap tests

## Goal
Create the nblaunch service skeleton under `services/nblaunch/` with package structure, app bootstrap, and initial route wiring.

## Why this stage exists
This stage establishes a runnable foundation and a functioning test harness before adding feature logic.

## Prerequisites
- Stage 01 approved.
- Target directory layout confirmed.

## Files and directories in scope
- `services/nblaunch/README.md`
- `services/nblaunch/Dockerfile`
- `services/nblaunch/requirements.txt`
- `services/nblaunch/pyproject.toml`
- `services/nblaunch/src/nblaunch/__init__.py`
- `services/nblaunch/src/nblaunch/app.py`
- `services/nblaunch/src/nblaunch/config.py`
- `services/nblaunch/src/nblaunch/handlers.py`
- `services/nblaunch/src/nblaunch/main.py`
- `services/nblaunch/tests/conftest.py`
- `services/nblaunch/tests/unit/test_config.py`
- `services/nblaunch/tests/integration/test_routes.py`

## Tasks for the AI
1. Create the full service directory structure in the required layout.

2. Implement application structure:


3. Wire required routes:

- `/healthz`
  - implemented
  - returns JSON `{ "ok": true }`
  - HTTP 200

- `/launch`
  - placeholder implementation
  - returns HTTP 501

- `/oauth_callback`
  - placeholder implementation
  - returns HTTP 501

4. Implement `config.py` loader that:
- reads environment variables
- validates required settings
- exposes typed settings object
- raises clear startup errors if configuration is invalid.

5. Add Dockerfile and packaging metadata.

Dockerfile requirements:
- base image `python:3.11-slim`
- working directory `/srv/nblaunch`
- install `requirements.txt`
- run application with `python -m nblaunch.main`

6. Add service README including:
- brief description
- local run instructions
- pytest commands
- docker build/run example

7. Add bootstrap tests:

Unit:
- `test_config.py` verifies configuration parsing and validation.

Integration:
- `test_routes.py` verifies:
  - `/healthz` returns HTTP 200
  - `/launch` returns HTTP 501
  - `/oauth_callback` returns HTTP 501

## Expected outputs
- Runnable service scaffold in the required package layout.
- Docker image builds successfully.
- Pytest test suite executes successfully.

## Acceptance criteria
- App boots locally and exposes all three routes.
- `/healthz` returns success payload.
- `/launch` intentionally returns `501`.
- `/oauth_callback` intentionally returns `501`.
- Tests verify route behavior and configuration parsing.
- No notebook download logic, HMAC validation, Hub API calls, or filesystem writes are implemented in this stage.

## Human review checklist
- Verify file structure matches required layout exactly.
- Verify bootstrap code is minimal and clean.
- Verify test harness is operational.
- Verify no premature implementation of launch logic.

## Common failure modes / things to watch
- Implementing launch logic too early.
- Mixing configuration parsing into handlers.
- Over-engineering the bootstrap stage.

## Suggested commit boundary
Commit scaffold + bootstrap tests only.

## Handoff to human
Pause for approval of structure, startup behavior, and initial test harness before implementing security logic.
