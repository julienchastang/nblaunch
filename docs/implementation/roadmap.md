# nblaunch roadmap

## Sequence
1. Stage 01: requirements and target layout
2. Stage 02: service scaffold and bootstrap tests
3. Stage 03: security and request validation
4. Stage 04: notebook fetch and storage
5. Stage 05: JupyterHub service OAuth wiring
6. Stage 06: home subpath and spawn hook
7. Stage 07: e2e validation and ops hardening

## Milestones
- M1: service scaffold boots with tests green (Stages 01-02)
- M2: request security and notebook persistence complete (Stages 03-04)
- M3: full Hub integration and URL behavior complete (Stages 05-06)
- M4: end-to-end verification and operational hardening complete (Stage 07)

## Dependencies
- Each stage depends on approvals and outputs from the previous stage.
- `spec/spec.md`, `spec/test-matrix.md`, and `spec/open-questions.md` remain authoritative across all stages.
