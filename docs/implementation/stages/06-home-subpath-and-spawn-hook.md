# Title
Stage 06 - Home-subpath API and spawn-hook integration with parallel tests

## Goal
Implement Hub-owned deterministic per-user home-subpath logic and integrate nblaunch with it so notebook writes land in the correct user storage path.

## Why this stage exists
Storage path correctness depends on strict consistency between JupyterHub spawn-time mount behavior and nblaunch home resolution. This boundary should be implemented and reviewed as a single unit.

## Prerequisites
- Stage 05 approved.
- Home volume mount names and mount paths confirmed for target deployment.

## Files and directories in scope
- `jupyterhub/base/extraConfig/21-home-subpath.py`
- `jupyterhub/base/extraConfig/22-nblaunch-home-subpath-api.py`
- `services/nblaunch/src/nblaunch/hubapi.py`
- `services/nblaunch/src/nblaunch/storage.py`
- `services/nblaunch/src/nblaunch/handlers.py`
- `services/nblaunch/tests/integration/test_home_subpath_resolution.py`
- `services/nblaunch/tests/unit/test_hubapi.py`
- `services/nblaunch/tests/unit/test_storage.py`

## Tasks for the AI
1. Implement deterministic `home_subpath_for(username)` logic in Hub extraConfig as the single source of truth for subpath generation.

2. Implement or compose the pre-spawn hook so it sets `subPath` for the configured home volume mount without overwriting existing hook behavior.

3. Implement a Hub API endpoint that:
   - is callable only by the `nblaunch` service identity
   - accepts the required request input for username lookup
   - returns the home-subpath mapping in the agreed response shape
   - rejects unauthorized callers

4. Implement `hubapi.py` in nblaunch so the service:
   - calls the Hub API endpoint
   - validates response shape and subpath format
   - resolves the effective user root from the returned subpath
   - does not reimplement the home-subpath algorithm locally

5. Update `handlers.py` and `storage.py` only as needed so notebook writes use the Hub-resolved user root while preserving existing path-safety guarantees.

6. Add tests for:
   - spawn-hook mount mutation behavior
   - subpath parity between Hub output and nblaunch consumption
   - authorization on the Hub API endpoint
   - malformed subpath rejection
   - representative username normalization edge cases

## Expected outputs
- Hub-owned home-subpath logic integrated into spawn behavior
- nblaunch home resolution via authenticated Hub API call
- Tests covering algorithm parity, authorization, and path-contract validation

## Acceptance criteria
- Spawn hook sets the expected user `subPath` for the configured home volume mount.
- Existing pre-spawn hook behavior is preserved or intentionally composed.
- The Hub API endpoint returns the agreed mapping shape and rejects unauthorized callers.
- nblaunch resolves and validates the same subpath contract without duplicating the algorithm.
- Integration tests verify the end-to-end home-subpath resolution path.
- Username normalization edge cases are covered by tests.

## Human review checklist
- Verify algorithm ownership stays on the Hub side.
- Verify hook composition with any existing pre-spawn logic.
- Verify mount selector assumptions (`name`, `mountPath`) are correct for the target deployment.
- Verify API authorization is restricted to the `nblaunch` service identity.
- Verify deterministic mapping and normalization behavior are acceptable.

## Common failure modes / things to watch
- Divergent subpath algorithms between Hub and service.
- Replacing existing pre-spawn hook logic by accident.
- Assuming hard-coded mount selector details that do not hold across deployments.
- Accepting malformed subpath strings from API responses.
- Letting nblaunch reconstruct logic that should remain Hub-owned.

## Suggested commit boundary
Commit Hub extraConfig, nblaunch Hub API integration, and parity/authorization tests together.

## Handoff to human
Pause for staging validation of spawn-hook behavior, API authorization, and path-resolution parity before final repo-level end-to-end validation and operational hardening.
