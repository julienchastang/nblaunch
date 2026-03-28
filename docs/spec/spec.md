# nblaunch Behavioral and Configuration Contract

## Scope
This document defines the current standalone behavior contract for the `nblaunch` service and its boundary with JupyterHub. It focuses on interfaces and externally visible behavior.

## Route Contracts

### `GET /healthz`
- Purpose: liveness probe for the nblaunch process.
- Authentication: none.
- Success response:
  - Status: `200 OK`
  - Content-Type: `application/json; charset=utf-8`
  - Body:
    ```json
    {"ok": true}
    ```

### `GET /launch`
- Purpose: validate a signed launch request, retrieve notebook content, place it in the requesting user home, and redirect the user into JupyterLab.
- Authentication:
  - Request authenticity is validated with HMAC over canonical query fields.
  - User identity comes from JupyterHub-authenticated request context or the nblaunch OAuth callback flow.

#### Request Contract
- Method: `GET`
- Required query parameters:
  - `nb`: notebook identifier from gallery/catalog.
  - `ts`: unix epoch seconds in UTC.
  - `sig`: lowercase hex HMAC-SHA256 digest.

#### Canonical Validation Rules
- `nb`
  - Must match `^[A-Za-z0-9._/-]{1,256}$`.
  - Must not contain `..`, start with `/`, or include a URL scheme.
- `ts`
  - Must parse as a base-10 integer seconds value.
  - Must be within `NBLAUNCH_SIGNATURE_TTL_SECONDS` of current UTC time.
- `sig`
  - Must match `^[a-f0-9]{64}$`.
  - Must equal the server-computed HMAC using constant-time comparison.
- HMAC base string: `nb=<nb>&ts=<ts>`.
- Secret key source: `NBLAUNCH_HMAC_SECRET`.

#### Success Flow
1. Resolve the current authenticated user, or redirect into Hub OAuth if no user context exists.
2. Parse and validate `nb`, `ts`, and `sig`.
3. Fetch notebook bytes from the gallery upstream.
4. Resolve the user home root from the Hub-owned home-subpath API.
5. Write the notebook atomically under the resolved user root.
6. Redirect to the saved notebook through JupyterHub.

#### Success Response
- Status: `302 Found`
- Header: `Location: <jupyterhub-base>/user-redirect/lab/tree/<relative-notebook-path>`
- Body: empty.

#### Failure Behavior
All failure responses for `/launch` are JSON:
- Content-Type: `application/json; charset=utf-8`
- Body shape:
  ```json
  {"error": {"code": "<stable_code>", "message": "<human_message>"}}
  ```

Status code and trigger contract:
- `400 Bad Request`
  - missing params
  - malformed params
  - invalid notebook ID
- `401 Unauthorized`
  - expired or invalid timestamp
  - invalid HMAC signature
- `403 Forbidden`
  - Hub home-subpath lookup is rejected for service authorization reasons
- `404 Not Found`
  - missing user home mapping
- `413 Payload Too Large`
  - notebook exceeds configured max size
- `502 Bad Gateway`
  - notebook download failure
  - invalid Hub API response
  - malformed Hub home-subpath payload
- `500 Internal Server Error`
  - filesystem write failure

#### Redirect Contract
- Redirect targets must be built only from server-controlled base paths plus validated relative notebook paths.
- No user-supplied host or absolute redirect target may be used.

### `GET /oauth_callback`
- Purpose: complete the JupyterHub-managed service OAuth handshake.
- Behavior:
  - validates callback `state`
  - exchanges the OAuth code for a Hub token
  - resolves the Hub user identity from that token
  - stores the resolved user in the service cookie
  - redirects back to the original destination or service root
- Success response:
  - `302 Found`
- Failure response:
  - `401 Unauthorized` when authenticated service context cannot be established.

## Module Responsibilities and Boundaries

### `config.py`
- Owns settings schema, env parsing, defaults, and startup validation.
- Must not perform network I/O.

### `security.py`
- Owns canonicalization, HMAC generation and verification, timestamp TTL validation, and constant-time comparison.
- Returns typed validation results or errors.

### `hubapi.py`
- Owns the Hub home-subpath lookup.
- Injects the service token for Hub API authorization.
- Validates the response shape before returning a resolved user root.

### `nbgallery.py`
- Owns notebook retrieval from the gallery upstream.
- Enforces content-type and size constraints.
- Returns notebook bytes and metadata.

### `storage.py`
- Owns safe path resolution, directory creation, and atomic file writes.
- Prevents traversal and namespace escape.

### `handlers.py`
- Owns HTTP handler orchestration and translation of domain errors into HTTP responses.

### `app.py`
- Owns the FastAPI app factory, route registration, and dependency assembly.

### `main.py`
- Owns runtime startup.

## Configuration Contract

### Required Environment Variables
- `NBLAUNCH_HMAC_SECRET`
- `NBLAUNCH_SERVICE_TOKEN`
- `NBLAUNCH_HUB_API_URL`
- `NBLAUNCH_GALLERY_BASE_URL`
- `NBLAUNCH_NOTEBOOK_BASE_DIR`

### Optional Environment Variables
- `NBLAUNCH_GALLERY_DOWNLOAD_PATH_TEMPLATE`
- `NBLAUNCH_GALLERY_USER_AGENT`
- `NBLAUNCH_SIGNATURE_TTL_SECONDS`
- `NBLAUNCH_MAX_NOTEBOOK_BYTES`
- `NBLAUNCH_GALLERY_TIMEOUT_SECONDS`
- `NBLAUNCH_HTTP_TIMEOUT_SECONDS`
- `NBLAUNCH_LOG_LEVEL`
- `NBLAUNCH_JUPYTERHUB_BASE_URL`

### Startup Failure Behavior
The process must exit before serving traffic when required settings are missing or invalid.

## JupyterHub Integration Contract

- JupyterHub remains the source of truth for authenticated user identity.
- nblaunch depends on a Hub endpoint at `/services/nblaunch/home-subpath/<username>` to return a JSON object containing:
  - `username`
  - `home_subpath`
- nblaunch must treat the Hub-provided home subpath as authoritative and must validate it before constructing local filesystem paths.
- nblaunch must surface Hub authorization failures distinctly from malformed or unavailable Hub responses.

## Trust and Ownership Summary
- Signature validity: owned by nblaunch.
- User identity and OAuth session: owned by JupyterHub.
- Home-subpath source of truth: owned by JupyterHub.
- Notebook content source of truth: owned by the gallery upstream.
- Final write-path safety: owned by nblaunch.
