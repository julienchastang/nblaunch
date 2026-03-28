# nblaunch Test Matrix

This standalone repo currently ships unit and integration coverage only. Historical Stage 01 references to `services/nblaunch/...`, `tests/smoke/`, and `tests/e2e/` came from the former monorepo and do not reflect the files present here.

## Current Test Inventory

| Layer | Files in this repo | Primary coverage |
|---|---|---|
| Unit | `tests/unit/test_config.py`, `tests/unit/test_hubapi.py`, `tests/unit/test_nbgallery.py`, `tests/unit/test_security.py`, `tests/unit/test_storage.py` | config parsing, Hub API response validation, gallery fetch handling, signature validation, storage safety |
| Integration | `tests/integration/test_routes.py`, `tests/integration/test_launch_handler.py`, `tests/integration/test_oauth_flow.py`, `tests/integration/test_home_subpath_resolution.py` | route registration, launch flow behavior, OAuth round-trips, Hub home-subpath integration |

## Route Coverage

| Route / Area | Coverage in this repo |
|---|---|
| `/healthz` and service root routes | `tests/integration/test_routes.py` |
| `/launch` request validation and auth redirects | `tests/integration/test_launch_handler.py`, `tests/integration/test_routes.py`, `tests/unit/test_security.py` |
| `/launch` gallery fetch, storage, and redirect behavior | `tests/integration/test_launch_handler.py`, `tests/unit/test_nbgallery.py`, `tests/unit/test_storage.py` |
| `/launch` Hub home-subpath resolution | `tests/integration/test_home_subpath_resolution.py`, `tests/unit/test_hubapi.py` |
| `/oauth_callback` flow and cookie/state handling | `tests/integration/test_oauth_flow.py`, `tests/integration/test_routes.py` |

## Coverage Expectations

- Every `/launch` failure condition implemented in the standalone service should have at least one unit or integration test in this repo.
- Smoke and end-to-end validation against a live JupyterHub deployment are still recommended operational checks, but those suites are not included here.
- Route and module contracts in this repo should stay aligned with the shipped unit and integration tests, not with historical monorepo-only test paths.
