# nblaunch Test Matrix (Stage 01)

## Route Coverage Matrix

| Area | Behavior / Failure Mode | Unit (`services/nblaunch/tests/unit/`) | Integration (`services/nblaunch/tests/integration/`) | Smoke / E2E (`tests/smoke/`, `tests/e2e/`) |
|---|---|---|---|---|
| `/healthz` | returns `200` with required JSON body and content type | `test_handlers_healthz.py::test_healthz_ok_contract` | `test_http_healthz.py::test_healthz_contract` | `tests/smoke/test_nblaunch_healthz.py::test_healthz_available` |
| `/healthz` | readiness failure returns `503` contract | `test_handlers_healthz.py::test_healthz_unavailable_contract` | `test_http_healthz.py::test_healthz_unavailable` | `tests/smoke/test_nblaunch_healthz.py::test_healthz_failure_signal` |
| `/launch` | happy path signs, fetches, writes, redirects `302` | `test_handlers_launch.py::test_launch_happy_path_redirect` | `test_launch_flow.py::test_launch_end_to_end_with_mocks` | `tests/e2e/test_launch_happy_path.py::test_launch_opens_notebook` |
| `/launch` | missing params -> `400` | `test_handlers_launch.py::test_missing_required_query_params` | `test_launch_validation.py::test_missing_params_400` | `tests/smoke/test_launch_validation.py::test_missing_params` |
| `/launch` | malformed params -> `400` | `test_security_validation.py::test_param_shape_validation` | `test_launch_validation.py::test_malformed_params_400` | `tests/smoke/test_launch_validation.py::test_malformed_params` |
| `/launch` | invalid notebook id -> `400` | `test_security_validation.py::test_nb_disallows_traversal` | `test_launch_validation.py::test_invalid_nb_400` | `tests/smoke/test_launch_validation.py::test_invalid_notebook_id` |
| `/launch` | expired/invalid timestamp -> `401` | `test_security_hmac.py::test_timestamp_ttl_enforced` | `test_launch_auth.py::test_expired_ts_401` | `tests/smoke/test_launch_auth.py::test_expired_timestamp_rejected` |
| `/launch` | invalid signature -> `401` | `test_security_hmac.py::test_signature_mismatch_unauthorized` | `test_launch_auth.py::test_invalid_sig_401` | `tests/smoke/test_launch_auth.py::test_invalid_signature_rejected` |
| `/launch` | notebook download failure -> `502` | `test_handlers_launch.py::test_gallery_failure_maps_to_502` | `test_launch_gallery.py::test_gallery_timeout_502` | `tests/e2e/test_launch_dependency_failures.py::test_gallery_unavailable` |
| `/launch` | notebook too large -> `413` | `test_nbgallery.py::test_size_limit_enforced` | `test_launch_gallery.py::test_large_notebook_413` | `tests/e2e/test_launch_dependency_failures.py::test_large_notebook_rejected` |
| `/launch` | invalid Hub API response -> `502` | `test_hubapi.py::test_invalid_user_payload_error` | `test_launch_hubapi.py::test_invalid_hub_payload_502` | `tests/e2e/test_launch_dependency_failures.py::test_hub_invalid_payload` |
| `/launch` | missing user home mapping -> `404` | `test_handlers_launch.py::test_missing_home_mapping_404` | `test_launch_hubapi.py::test_missing_home_mapping_404` | `tests/e2e/test_launch_dependency_failures.py::test_missing_home_mapping` |
| `/launch` | filesystem write failure -> `500` | `test_storage.py::test_write_failure_surfaces_internal_error` | `test_launch_storage.py::test_write_error_500` | `tests/e2e/test_launch_dependency_failures.py::test_storage_failure` |
| `/oauth_callback` | oauth callback success redirect behavior | `test_handlers_oauth.py::test_oauth_callback_success` | `test_oauth_callback.py::test_oauth_callback_roundtrip` | `tests/smoke/test_oauth_callback.py::test_callback_route_live` |
| `/oauth_callback` | oauth callback auth failure -> `401` | `test_handlers_oauth.py::test_oauth_callback_unauthorized` | `test_oauth_callback.py::test_oauth_callback_401` | `tests/e2e/test_oauth_failures.py::test_callback_without_valid_context` |

## Module Coverage Matrix

| Module | Unit Test Focus | Integration Test Focus |
|---|---|---|
| `config.py` | required envs, defaults, type/range parsing, secret redaction | app startup fails-fast on invalid config |
| `security.py` | canonical string creation, HMAC verify, constant-time compare, TTL windows | handler mapping from validation errors to `400`/`401` |
| `hubapi.py` | auth header usage, response schema validation, error mapping | live/stub Hub API behavior and failure translation to `502`/`404` |
| `nbgallery.py` | upstream fetch error classes, size-limit accounting | launch flow against stub gallery with timeout/non-2xx/oversize |
| `storage.py` | path normalization, traversal prevention, atomic write operations | file write in temp sandbox and injected write failures |
| `handlers.py` | exact status codes and error payload contracts | full route behavior with mocked dependencies |
| `app.py` | route registration and middleware wiring | app factory boot with test config |
| `main.py` | startup invocation and exit on config failures | process-level startup smoke checks |

## Cross-Cutting Security and Reliability Cases

| Case | Unit | Integration | E2E |
|---|---|---|---|
| HMAC canonicalization drift prevention | `test_security_hmac.py::test_exact_canonical_order` | `test_launch_auth.py::test_signed_url_roundtrip` | `tests/e2e/test_launch_happy_path.py::test_signed_link_generated_and_consumed` |
| Timestamp skew handling near boundary | `test_security_hmac.py::test_ttl_boundary_conditions` | `test_launch_auth.py::test_ttl_boundary` | `tests/e2e/test_launch_auth_boundaries.py::test_ttl_boundary` |
| Redirect safety (no open redirect) | `test_handlers_launch.py::test_redirect_uses_server_base_only` | `test_launch_validation.py::test_host_injection_ignored` | `tests/e2e/test_security_regressions.py::test_no_open_redirect` |
| Path traversal prevention | `test_storage.py::test_rejects_parent_segments` | `test_launch_storage.py::test_traversal_nb_rejected` | `tests/e2e/test_security_regressions.py::test_cross_user_path_blocked` |
| Upstream timeout resilience | `test_nbgallery.py::test_timeout_classification` | `test_launch_gallery.py::test_timeout_to_502` | `tests/e2e/test_launch_dependency_failures.py::test_gallery_timeout` |

## Coverage Expectations
- Every `/launch` failure condition in `spec.md` must have at least one unit and one integration test.
- `tests/smoke/` must verify service liveness and basic launch validation behavior in deployed-like environments.
- `tests/e2e/` must verify user-visible launch behavior and key dependency failure paths.
- Route and module contracts are blocking: implementation stages should not proceed without matching test definitions.
