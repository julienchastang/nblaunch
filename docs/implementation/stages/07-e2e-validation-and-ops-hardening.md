# Title
Stage 07 - End-to-end validation, documentation, and operational hardening

## Goal
Finalize nblaunch deployment assets and operational readiness with smoke and end-to-end validation guidance, operator-facing documentation, and hardening review.

## Why this stage exists
The feature is complete only when humans can deploy it, validate it, troubleshoot it, and roll it back safely.

## Prerequisites
- Stage 06 approved.
- Staging validation completed for launch flow and storage-path behavior.

## Files and directories in scope
- `services/nblaunch/k8s/deployment.yaml`
- `services/nblaunch/k8s/service.yaml`
- `services/nblaunch/k8s/secret.example.yaml`
- `services/nblaunch/scripts/generate_nblaunch_url.sh`
- `services/nblaunch/README.md`
- `jupyterhub/README.md`
- `tests/smoke/test_nblaunch_config_render.py`
- `tests/e2e/test_nblaunch_open_in_hub.py`

## Tasks for the AI
1. Finalize Kubernetes manifests for nblaunch service deployment without redesigning earlier service or Hub integration contracts.

2. Add a helper script for generating signed launch URLs.

3. Write operator-facing documentation covering:
   - required secrets and configuration inputs
   - image build and deployment steps
   - rollout and verification steps
   - rollback steps
   - troubleshooting workflow
   - common configuration mismatches and failure modes

4. Add or complete repo-level validation coverage:
   - always-on smoke tests for config render and coherence checks
   - environment-dependent end-to-end validation for signed launch through the Hub path
   - clearly document execution expectations and prerequisites for each test class

5. Document runtime tuning and hardening controls, including:
   - TTL
   - max notebook size
   - logging and timeout behavior
   - cookie secret, HMAC secret, and service-token handling
   - token and secret rotation expectations

## Expected outputs
- Deployment assets suitable for staged rollout and production review
- Operator documentation with deployment, verification, rollback, and troubleshooting guidance
- Smoke and environment-aware e2e validation coverage

## Acceptance criteria
- Operators can deploy and validate nblaunch using the provided documentation.
- Documentation includes explicit rollout, verification, rollback, and troubleshooting steps.
- Smoke tests cover config/render coherence for the critical service path.
- End-to-end validation guidance or tests cover the signed-launch-through-Hub path with clearly stated prerequisites.
- Security-sensitive settings are documented clearly without exposing secrets.
- No real secrets or environment-specific production values are committed.

## Human review checklist
- Verify manifests align with cluster conventions.
- Verify docs are sufficient for on-call and staged rollout use.
- Verify smoke and e2e checks are stable, realistic, and clearly scoped.
- Verify rollback and incident response steps are explicit and practical.
- Verify no production-only values leaked into base assets.

## Common failure modes / things to watch
- Missing rollback details.
- Environment-specific values leaked into base manifests.
- E2E tests that depend on brittle or undocumented manual setup.
- Documentation that explains what the service is but not how to operate it.
- Hardening guidance that omits token or secret lifecycle expectations.

## Suggested commit boundary
Commit Kubernetes manifests, helper scripts, operator documentation, and final smoke/e2e validation artifacts.

## Handoff to human
Request final production-readiness review and sign-off.
