# nblaunch Behavioral and Configuration Contract

## Scope
This document defines the Stage 01 behavior contract for the `nblaunch` service and its integration with JupyterHub. It intentionally defines interfaces and expected behavior only.

## Route Contracts

### `GET /healthz`
- Purpose: Liveness and readiness probe for the nblaunch process.
- Authentication: none.
- Success response:
  - Status: `200 OK`
  - Content-Type: `application/json; charset=utf-8`
  - Body:
    ```json
    {"status":"ok","service":"nblaunch"}
    ```
- Failure response:
  - Status: `503 Service Unavailable`
  - Content-Type: `application/json; charset=utf-8`
  - Body includes machine-readable error code and message.

### `GET /launch`
- Purpose: Validate a signed launch request, retrieve notebook content, place it in the requesting user home, and redirect user to the opened notebook in JupyterLab.
- Authentication:
  - Request authenticity is validated with HMAC signature over canonical query fields.
  - User identity comes from JupyterHub-authenticated request context and Hub API lookup.

#### Request Contract
- Method: `GET`
- Required query parameters:
  - `nb`: notebook identifier from gallery/catalog.
  - `ts`: unix epoch seconds in UTC.
  - `sig`: lowercase hex HMAC-SHA256 digest.
- No additional query parameters are required for contract compliance.

#### Canonical Validation Rules
- `nb`
  - Must match: `^[A-Za-z0-9._/-]{1,256}$`
  - Must not contain `..`, start with `/`, or include URL scheme (`://`).
- `ts`
  - Must parse as base-10 integer seconds.
  - Must be within `NBLAUNCH_SIGNATURE_TTL_SECONDS` of current UTC time.
- `sig`
  - Must match: `^[a-f0-9]{64}$`
  - Must equal server-computed HMAC using shared secret and constant-time compare.
- HMAC base string (exact order): `nb=<nb>&ts=<ts>`.
- Secret key source: `NBLAUNCH_HMAC_SECRET`.

#### Success Flow
1. Parse and validate `nb`, `ts`, `sig`.
2. Verify signature and TTL.
3. Resolve current hub user and fetch user model from Hub API.
4. Resolve user home subpath from Hub response (source of truth: user model metadata).
5. Fetch notebook bytes/stream from gallery service by `nb`.
6. Enforce max payload size before disk write.
7. Create destination directory if missing under configured base path.
8. Write notebook atomically to `<resolved-user-home>/<target-file>.ipynb`.
9. Redirect to JupyterLab URL for that saved notebook path.

#### Success Response
- Status: `302 Found`
- Header: `Location: <jupyterhub-base>/user/<username>/lab/tree/<relative-notebook-path>`
- Body: empty.

#### Failure Behavior
All failure responses for `/launch` are JSON:
- Content-Type: `application/json; charset=utf-8`
- Body shape:
  ```json
  {"error":{"code":"<stable_code>","message":"<human_message>"}}
  ```

Status code and trigger contract:
- `400 Bad Request`
  - missing params: one or more of `nb`, `ts`, `sig` absent.
  - malformed params: regex/type parse failure for `nb`, `ts`, or `sig`.
  - invalid notebook ID: `nb` violates traversal/scheme/path rules.
- `401 Unauthorized`
  - expired or invalid timestamp: `ts` outside TTL window.
  - invalid HMAC signature: computed signature mismatch.
- `502 Bad Gateway`
  - notebook download failure: upstream gallery timeout, non-2xx, or transport error.
  - invalid Hub API response: missing required fields or non-2xx from Hub user endpoint.
- `404 Not Found`
  - missing user home mapping: user model lacks required home-subpath mapping.
- `413 Payload Too Large`
  - notebook too large: downloaded size exceeds configured max.
- `500 Internal Server Error`
  - filesystem write failure: mkdir, temp write, fsync, rename, or permission failure.

#### Redirect Contract
- Redirect target must only use server-constructed path parts.
- No user-supplied absolute URL or host is allowed in redirect construction.

### `GET /oauth_callback`
- Purpose: service endpoint required by JupyterHub-managed service OAuth handshake.
- Behavior model:
  - Accept callback from Hub OAuth flow.
  - Delegate token/session establishment to JupyterHub service auth integration.
  - On successful auth completion, continue to original destination (`/launch` workflow or default service root).
- Success response:
  - Usually redirect (`302`) per Hub OAuth flow.
- Failure response:
  - `401` when callback cannot establish authenticated service context.

## Module Responsibilities and Boundaries

### `config.py`
- Owns settings schema, env parsing, default assignment, and startup validation.
- Exposes typed read-only configuration object to other modules.
- Must not perform network I/O.

### `security.py`
- Owns canonicalization, HMAC generation/verification, timestamp TTL validation, and constant-time comparisons.
- Returns typed validation results/errors; no HTTP responses here.

### `hubapi.py`
- Owns Hub API client behavior for current user resolution.
- Handles auth header injection using service token.
- Converts Hub payloads into minimal typed model used by handlers/storage.

### `nbgallery.py`
- Owns notebook retrieval from gallery upstream and response normalization.
- Enforces max-download-size stream accounting.
- Returns notebook bytes/stream and metadata; no filesystem writes.

### `storage.py`
- Owns safe local path resolution, directory creation, and atomic file write.
- Prevents path traversal and cross-user writes.
- Returns final relative path for redirect generation.

### `handlers.py`
- Owns HTTP route handlers and translation of domain errors into status codes.
- Composes `security`, `hubapi`, `nbgallery`, and `storage`.
- Must be thin orchestration; no duplicated domain logic.

### `app.py`
- Owns framework app factory, middleware wiring, route registration, and dependency assembly.

### `main.py`
- Owns runtime entrypoint and process startup.
- Must fail fast on invalid config before serving traffic.

## Configuration Contract

### Required Environment Variables
- `NBLAUNCH_HMAC_SECRET` (secret): shared key for launch-link signatures.
- `NBLAUNCH_SERVICE_TOKEN` (secret): token for Hub API service authorization.
- `NBLAUNCH_HUB_API_URL` (non-secret): base URL for Hub API.
- `NBLAUNCH_NOTEBOOK_BASE_DIR` (non-secret): filesystem root for user notebook writes.

### Optional Environment Variables
- `NBLAUNCH_SIGNATURE_TTL_SECONDS` (default: `300`)
- `NBLAUNCH_MAX_NOTEBOOK_BYTES` (default: `10485760`)
- `NBLAUNCH_GALLERY_TIMEOUT_SECONDS` (default: `10`)
- `NBLAUNCH_HTTP_TIMEOUT_SECONDS` (default: `10`)
- `NBLAUNCH_LOG_LEVEL` (default: `INFO`)
- `NBLAUNCH_JUPYTERHUB_BASE_URL` (default: `/`)

### Secret Classification
- Secrets:
  - `NBLAUNCH_HMAC_SECRET`
  - `NBLAUNCH_SERVICE_TOKEN`
- Non-secrets:
  - all other configuration values above.

### Startup Failure Behavior
Process must exit non-zero before binding network socket when:
- a required variable is missing,
- an integer setting is non-integer or out of valid range,
- URL settings are malformed,
- notebook base directory setting is empty or not absolute.

## JupyterHub Integration Contract

### `jupyterhub/base/extraConfig/21-home-subpath.py`
- Ownership: JupyterHub side.
- Responsibility: derive and persist per-user home subpath metadata at spawn/user-model time.
- Trust boundary: nblaunch trusts only this server-side metadata, not request parameters.

### `jupyterhub/base/extraConfig/22-nblaunch-home-subpath-api.py`
- Ownership: JupyterHub side.
- Responsibility: expose/normalize home-subpath information in a Hub API-visible user model field consumed by nblaunch.
- Trust boundary: only Hub-authenticated service tokens may read user model data.

### `jupyterhub/services/nblaunch.yaml`
- Ownership: JupyterHub deployment config.
- Responsibility: register nblaunch as managed/external service, wire OAuth callback URL, and provide service token/env.
- Authorization expectations:
  - Service token must be scoped minimally to read current user model needed for home-subpath resolution.
  - nblaunch must reject Hub API calls that fail authorization and surface `502` at `/launch` per contract.

## Trust and Ownership Summary
- Signature validity: owned by nblaunch (`security.py`).
- User identity/session: owned by JupyterHub OAuth/service auth.
- Home-subpath source of truth: JupyterHub user model fields set by extraConfig.
- Notebook content source of truth: gallery upstream.
- Final write location safety: owned by nblaunch storage path policy.
