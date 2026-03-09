# Title
Stage 03 - Security and request validation layer with parallel tests

## Goal
Implement signed launch-request validation for `/launch` in a dedicated security layer and verify it with comprehensive unit and integration tests.

## Why this stage exists
Request validation is the highest-risk part of the service and should be isolated, tested, and reviewed before any notebook download, Hub API access, or filesystem write behavior is enabled.

## Prerequisites
- Stage 02 approved.
- Security and configuration contract from Stage 01 approved.

## Files and directories in scope
- `services/nblaunch/src/nblaunch/security.py`
- `services/nblaunch/src/nblaunch/handlers.py`
- `services/nblaunch/src/nblaunch/config.py`
- `services/nblaunch/tests/unit/test_security.py`
- `services/nblaunch/tests/integration/test_launch_handler.py`

## Tasks for the AI
1. Implement security primitives in `security.py` for the `/launch` request:
   - required query parameter validation for `nb`, `ts`, and `sig`
   - notebook ID validation
   - timestamp parsing and TTL validation
   - HMAC-SHA256 signature verification using the canonical message format `"{nb}:{ts}"`
   - constant-time signature comparison

2. Make validation logic testable and deterministic:
   - avoid hidden time dependencies where practical
   - structure code so timestamp checks can be tested predictably

3. Integrate validation into the `/launch` handler path so it runs before any network or file operations.

4. Implement explicit HTTP error mappings for:
   - missing params
   - malformed params
   - invalid notebook ID
   - invalid timestamp
   - expired or not-yet-valid timestamp
   - invalid signature

5. Preserve separation of responsibilities:
   - `handlers.py` orchestrates request flow and translates validation failures into HTTP behavior
   - `security.py` performs validation and signature checks
   - no notebook download, Hub API calls, or filesystem writes are implemented in this stage

## Expected outputs
- Security validation layer integrated into `/launch`
- Deterministic unit tests for validation behavior
- Integration tests proving `/launch` rejects invalid requests before any side effects

## Acceptance criteria
- A valid signed request passes the validation path.
- Missing parameters fail with documented 4xx behavior.
- Invalid signature, invalid timestamp, expired or not-yet-valid timestamp, and invalid notebook ID each fail with specific documented 4xx behavior.
- Signature generation and verification use the exact canonical message format `"{nb}:{ts}"`.
- Constant-time signature comparison is used.
- No notebook download, Hub API call, or filesystem write occurs before validation succeeds.

## Human review checklist
- Verify canonical HMAC message construction.
- Verify constant-time comparison behavior.
- Verify TTL semantics and clock-skew expectations.
- Verify rejected requests trigger no side effects.
- Verify validation behavior matches the Stage 01 contract.

## Common failure modes / things to watch
- Inconsistent message format used for signature generation and verification.
- Weak notebook ID validation enabling path-like input.
- Hidden dependence on wall-clock time that makes tests flaky.
- Ambiguous or inconsistent HTTP status mappings.
- Side-effecting code executed before validation completes.

## Suggested commit boundary
Commit only security-layer implementation and matching tests.

## Handoff to human
Request a security-focused review of `/launch` validation behavior before enabling notebook fetch, Hub API, or filesystem write behavior.
