# Title
Stage 01 - Behavioral contract, architecture boundaries, and test matrix

## Goal
Define the nblaunch behavioral contract and lock the target architecture in `usg-jupyter-configs` before implementation begins.

## Why this stage exists
A from-scratch rebuild needs an approved behavior contract, module boundary map, and test strategy before code is written, so later stages can be implemented and validated predictably.

## Non-goals
- Do not add implementation code.
- Do not create production scaffolding beyond planning documents.
- Do not decide CI/CD or deployment automation details beyond identifying dependencies and assumptions.

## Prerequisites
- Repository uses this target layout:
  - `services/nblaunch/...`
  - `jupyterhub/...`
  - repo-level `tests/smoke` and `tests/e2e`
- Required service routes are fixed:
  - `/healthz`
  - `/launch`
  - `/oauth_callback`

## Files and directories in scope
- `docs/nblaunch/spec/spec.md`
- `docs/nblaunch/spec/test-matrix.md`
- `docs/nblaunch/spec/open-questions.md`
- `services/nblaunch/src/nblaunch/` (referenced for design only; do not create implementation files)
- `jupyterhub/` (referenced for design only; do not create implementation files)

## Tasks for the AI
1. Write `spec.md` with explicit endpoint behavior:
   - `/healthz`: response body, content type, and status code contract.
   - `/launch`: exact request contract, including required query params (`nb`, `ts`, `sig`), validation rules, download flow, user-home resolution flow, write flow, and redirect flow.
   - `/oauth_callback`: role in JupyterHub OAuth flow and expected handling model.
2. In `spec.md`, define exact success and failure behavior for `/launch`, including status codes and trigger conditions for:
   - missing params
   - malformed params
   - invalid notebook ID
   - expired or invalid timestamp
   - invalid HMAC signature
   - notebook download failure
   - notebook too large
   - invalid Hub API response
   - missing user home mapping
   - filesystem write failure
3. Define module responsibilities and interface boundaries for:
   - `config.py`
   - `security.py`
   - `hubapi.py`
   - `nbgallery.py`
   - `storage.py`
   - `handlers.py`
   - `app.py`
   - `main.py`
4. Define the configuration contract:
   - required and optional environment variables
   - default values
   - which values are secrets
   - startup failure behavior for missing or malformed settings
5. Define the JupyterHub integration contract for:
   - `jupyterhub/base/extraConfig/21-home-subpath.py`
   - `jupyterhub/base/extraConfig/22-nblaunch-home-subpath-api.py`
   - `jupyterhub/services/nblaunch.yaml`
   Include trust boundaries, ownership of logic, and service-token authorization expectations.
6. Write `test-matrix.md` mapping each route, module, and major failure mode to:
   - unit tests in `services/nblaunch/tests/unit/`
   - integration tests in `services/nblaunch/tests/integration/`
   - smoke/e2e tests in `tests/smoke/` and `tests/e2e/`
7. Write `open-questions.md` capturing unresolved operational decisions, assumptions, and risks. Tag each item as:
   - confirmed assumption
   - unresolved decision
   - risk needing validation

## Expected outputs
- `spec.md` with a complete behavioral and configuration contract
- `test-matrix.md` with route-, module-, and failure-mode-based coverage mapping
- `open-questions.md` with unresolved operational items clearly categorized

## Acceptance criteria
- All three required routes are fully specified.
- `/launch` includes explicit success and failure behavior with defined status codes.
- Every module has defined responsibilities and boundary expectations.
- Security-sensitive controls, including HMAC, TTL, OAuth, and service-token authorization, are explicitly specified.
- The test matrix covers happy path, validation failures, authorization failures, external dependency failures, and filesystem behavior.
- This stage produces documentation only; no implementation code or test code is added.

## Human review checklist
- Approve endpoint behavior definitions.
- Approve error handling and status code definitions.
- Approve module boundaries and ownership of validation logic.
- Approve the configuration contract and secret classification.
- Approve JupyterHub trust boundaries and integration design.
- Approve test matrix completeness and reviewability.
- Approve unresolved questions and risks list.

## Common failure modes / things to watch
- Starting code without an agreed behavior contract.
- Vague or inconsistent `/launch` error behavior.
- Blurry ownership between service code and JupyterHub config.
- Missing startup-config failure behavior.
- Test mapping that names files but misses real failure modes.

## Suggested commit boundary
Commit only planning docs:
- `docs/nblaunch/spec/spec.md`
- `docs/nblaunch/spec/test-matrix.md`
- `docs/nblaunch/spec/open-questions.md`

## Handoff to human
Stop and request explicit approval of the behavioral contract, architecture boundaries, and test strategy before creating service scaffolding.
