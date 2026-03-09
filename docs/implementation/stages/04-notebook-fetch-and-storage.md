# Title
Stage 04 - Notebook retrieval and storage primitives with provisional launch integration

## Goal
Implement notebook retrieval from NBGallery and safe notebook writes to a caller-supplied user root, then integrate these into `/launch` after security checks.

## Why this stage exists
Network and file I/O concerns should be added only after request validation is stable, and before JupyterHub-specific home-resolution logic is introduced.

## Prerequisites
- Stage 03 approved.
- Fixture files prepared:
  - `services/nblaunch/tests/fixtures/sample_notebook.ipynb`
  - `services/nblaunch/tests/fixtures/oversized_notebook.ipynb`
  - `services/nblaunch/tests/fixtures/bad_html_response.html`

## Files and directories in scope
- `services/nblaunch/src/nblaunch/nbgallery.py`
- `services/nblaunch/src/nblaunch/storage.py`
- `services/nblaunch/src/nblaunch/handlers.py`
- `services/nblaunch/tests/unit/test_nbgallery.py`
- `services/nblaunch/tests/unit/test_storage.py`
- `services/nblaunch/tests/integration/test_launch_handler.py`
- `services/nblaunch/tests/fixtures/*`

## Tasks for the AI
1. Implement `nbgallery.py` client logic:
   - download notebook by ID
   - handle request timeout and upstream failure cases
   - reject unexpected HTML content type
   - enforce max payload size using both header-based and payload-based checks where applicable

2. Implement `storage.py` write logic:
   - accept a caller-supplied `user_root`
   - compute destination path under `<user_root>/nbgallery/<nb>.ipynb`
   - enforce path-safety constraints
   - perform atomic write using temporary file + replace

3. Extend `/launch` handler orchestration:
   - security validation
   - notebook download
   - notebook write
   - redirect to JupyterHub user-redirect lab tree path

4. Keep responsibility boundaries clear:
   - `nbgallery.py` owns remote fetch behavior and remote-response validation
   - `storage.py` owns destination-path construction and persistence safety
   - `handlers.py` orchestrates only

5. Keep JupyterHub-specific user-home resolution out of scope for this stage:
   - no Hub API calls
   - no home-subpath resolution logic
   - use provisional or injected user-root behavior for handler integration and tests

## Expected outputs
- Notebook retrieval and storage modules with clear boundaries
- Launch flow works through validation, fetch, write, and redirect using a provisional user-root strategy
- Unit and integration tests cover happy path and major I/O failure modes

## Acceptance criteria
- Happy-path request downloads notebook, writes it under the expected provisional user-root path, and returns redirect.
- Oversized content and bad content type are rejected safely.
- Fetch failures do not trigger writes.
- Storage failures do not trigger redirect.
- Storage writes are atomic and path-safe.
- Redirect target matches the Stage 01 contract.

## Human review checklist
- Verify failure-path status codes and messages.
- Verify remote-response validation behavior.
- Verify file-write safety, including no traversal and no partial writes.
- Verify collaborator boundaries remain clean.
- Verify no JupyterHub home-resolution logic has been added prematurely.

## Common failure modes / things to watch
- Blocking event loop with unexamined synchronous I/O in handler path.
- Trusting upstream content type or payload size too loosely.
- Writing directly to final path without atomic replace.
- Letting `storage.py` infer user-home logic that belongs to a later stage.
- Redirecting after a failed or partial write.

## Suggested commit boundary
Commit retrieval and storage modules, handler integration, fixtures, and matching tests.

## Handoff to human
Pause for review of I/O safety, collaborator boundaries, and provisional launch-path reliability before adding JupyterHub-specific home-resolution wiring.
