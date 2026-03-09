# Title
Stage 05 - JupyterHub service registration and OAuth wiring with parallel tests

## Goal
Register nblaunch as a JupyterHub service, wire OAuth callback handling, and require authenticated access to protected service routes.

## Why this stage exists
OAuth, scopes, route protection, and service registration form a distinct security boundary that should be reviewed before Hub-specific home-resolution logic is added.

## Prerequisites
- Stage 04 approved.
- Target JupyterHub config locations confirmed.

## Files and directories in scope
- `jupyterhub/README.md`
- `jupyterhub/services/nblaunch.yaml`
- `jupyterhub/base/values.yaml` (only if required by the repository's existing config structure)
- `jupyterhub/overlays/prod/nblaunch.yaml` (only if environment-specific override is needed)
- `services/nblaunch/src/nblaunch/handlers.py`
- `services/nblaunch/src/nblaunch/app.py`
- `services/nblaunch/tests/integration/test_oauth_flow.py`
- `tests/smoke/test_nblaunch_config_render.py`

## Tasks for the AI
1. Add Hub service registration in `jupyterhub/services/nblaunch.yaml`:
   - service name
   - service URL
   - OAuth client ID
   - OAuth callback URL
   - service API token reference

2. Add role and scope bindings using least privilege.

3. Wire `/oauth_callback` in the service app using the intended JupyterHub OAuth callback handling model.

4. Require authenticated access to protected service routes:
   - `/launch` must require authenticated user context
   - unauthenticated access must follow the expected Hub login/OAuth flow

5. Add environment-specific overrides under `jupyterhub/overlays/...` only where needed and avoid hardcoding production-only values into base config.

6. Add smoke and integration tests that validate:
   - service registration coherence
   - callback URL alignment
   - service/client identifier alignment
   - scope and role presence
   - authenticated route protection behavior

## Expected outputs
- Complete JupyterHub service registration
- OAuth callback route wired in the service
- Protected-route authentication behavior defined and tested
- Smoke tests proving config coherence

## Acceptance criteria
- Hub config includes a valid nblaunch service registration.
- `/oauth_callback` is wired and no longer returns placeholder behavior.
- Protected routes require authenticated user context.
- Smoke tests validate service name, URL, callback URI, client ID, token reference, and scope/role alignment.
- No real secrets are committed.
- No home-subpath API handler, pre-spawn hook, or user-root resolution logic is added in this stage.

## Human review checklist
- Verify callback URL and service prefix correctness.
- Verify least-privilege scopes and roles.
- Verify service/client/token alignment across service and Hub config.
- Verify unauthenticated access behavior for protected routes.
- Verify base vs overlay configuration boundaries are sensible.

## Common failure modes / things to watch
- Token or client-ID mismatch between service and Hub config.
- Overly broad scopes.
- Hardcoded production hostnames in base config.
- Mixing home-resolution logic into the OAuth/service-registration stage.
- Route protection behavior that differs from the Stage 01 contract.

## Suggested commit boundary
Commit JupyterHub service wiring, OAuth callback integration, protected-route auth behavior, and matching tests/smoke checks.

## Handoff to human
Request explicit security review of service registration, route protection, callback wiring, and scope design before enabling home-subpath API and spawn-hook integration.
