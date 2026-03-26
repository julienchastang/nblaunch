# Title
Stage 08 - Production rollout completion for auth, routing, and shared-home writes

## Goal
Complete the nblaunch production rollout from the Stage 07 baseline so that:
- authenticated access works end to end through JupyterHub service OAuth
- the real authenticated Hub username is used throughout the launch flow
- notebooks are fetched from the real gallery endpoint
- notebooks are written into the same shared home storage seen by single-user servers
- deployment assets match the live cluster topology

## Why this stage exists
Stage 07 established rollout assets, but the real deployment requires several production-alignment corrections that were not fully encoded there:

1. The service must be reachable on the prefixed path `/services/nblaunch/...`, and OAuth callback routing must match that prefix exactly.
2. `NBLAUNCH_HUB_API_URL` must point at the Hub origin, not an already-suffixed `/hub/api` path, because the service derives additional Hub endpoints from that base.
3. The callback handler cannot rely on Hub browser cookies on `/services/nblaunch/oauth_callback`; it must exchange the OAuth code for a token and use that token to resolve the authenticated Hub user.
4. The launch flow must reject the legacy placeholder username `oauth-authenticated-user` and consistently prefer the real Hub username.
5. The nblaunch pod must mount the same shared NFS namespace used for user homes, from the correct root, so notebook writes land where JupyterLab can see them.

This stage captures only the essential production corrections required to reach the working state.

## Prerequisites
- Stage 07 approved.
- The cluster runs nblaunch as a JupyterHub-managed service.
- JupyterHub service registration uses:
  - service name `nblaunch`
  - OAuth client ID `service-nblaunch`
  - redirect URI `/services/nblaunch/oauth_callback`
- The live storage topology is known and fixed:
  - single-user pods mount per-user NFS exports such as `/users/<normalized-user>` onto `/home/jovyan`
  - the nblaunch pod mounts the NFS root export `/` onto `/home`
  - therefore the nblaunch-visible home for user `<normalized-user>` is `/home/users/<normalized-user>`

## Files and directories in scope
- `services/nblaunch/src/nblaunch/app.py`
- `services/nblaunch/src/nblaunch/config.py`
- `services/nblaunch/src/nblaunch/handlers.py`
- `services/nblaunch/src/nblaunch/hubapi.py`
- `services/nblaunch/k8s/deployment.yaml`
- `services/nblaunch/tests/integration/test_oauth_flow.py`
- `services/nblaunch/tests/integration/test_routes.py`
- `services/nblaunch/tests/integration/test_home_subpath_resolution.py`
- `services/nblaunch/tests/unit/test_config.py`
- `jupyterhub/base/extraConfig/21-home-subpath.py`
- `jupyterhub/base/extraConfig/22-nblaunch-home-subpath-api.py`
- `jupyterhub/values-nblaunch.yaml`

## Required implementation details

### 1. Service path and callback alignment
The service must support both root and service-prefixed routes, but production traffic must work correctly on the prefixed paths:
- `/services/nblaunch/`
- `/services/nblaunch/healthz`
- `/services/nblaunch/launch`
- `/services/nblaunch/oauth_callback`

The OAuth authorize redirect must use:
- `client_id=service-nblaunch`
- `redirect_uri=/services/nblaunch/oauth_callback`

The app’s callback path handling must match the JupyterHub service configuration exactly. Do not rely on an unprefixed callback URL in production.

### 2. Real gallery configuration
Replace any placeholder gallery fetch configuration with real settings loaded from environment:
- `NBLAUNCH_GALLERY_BASE_URL`
- `NBLAUNCH_GALLERY_DOWNLOAD_PATH_TEMPLATE`
- `NBLAUNCH_GALLERY_USER_AGENT`

The app should use those settings for notebook download requests.

### 3. Correct Hub API base handling
`NBLAUNCH_HUB_API_URL` must be treated as the Hub origin/base, not as a pre-expanded user endpoint.

The deployment must set:
- `NBLAUNCH_HUB_API_URL=http://hub:8081`

Do not hardcode:
- `http://hub:8081/hub/api`

The service code must derive:
- `/hub/api/user`
- `/hub/api/oauth2/token`
- `/hub/api/oauth2/authorize`
- `/services/nblaunch/home-subpath/<username>`

from the configured base plus `NBLAUNCH_JUPYTERHUB_BASE_URL=/hub`.

### 4. Hub network reachability
The nblaunch pod must be allowed to reach the Hub directly.

Ensure the deployment pod template includes:
- `hub.jupyter.org/network-access-hub: "true"`

### 5. Hub-owned home-subpath mapping
Keep the Hub-owned deterministic home-subpath mapping based on normalized usernames:
- `users/<normalized-user>`

The Hub-side API must expose:
- `/services/nblaunch/home-subpath/<username>`

and return JSON:
- `username`
- `home_subpath`

The pre-spawn hook must apply the same home-subpath to the intended user-home mount in the single-user pod.

The mount-selection logic should be resilient enough to identify the correct home mount by:
- exact volume name + mount path match first
- then mount path
- then notebook_dir
- then volume name

### 6. Real authenticated user resolution in launch
The launch flow must not trust the legacy placeholder value:
- `oauth-authenticated-user`

It must:
- reject the placeholder from cookies
- reject the placeholder from headers
- prefer the live Hub user when that can be resolved
- only fall back to a forwarded-user header if no live Hub identity is available
- use the resolved real username for home-subpath lookup and notebook destination construction

### 7. OAuth callback must exchange the code
This is mandatory.

The callback handler must:
1. validate the stored OAuth state
2. read the `code` query parameter
3. `POST` the code to JupyterHub at `/hub/api/oauth2/token`
4. use the returned access token to `GET /hub/api/user`
5. extract the real Hub username from the token-authenticated user response
6. set the nblaunch service cookie to that real username
7. redirect back to the stored original launch URL

Do not attempt to resolve the user during callback by forwarding browser cookies from the callback request to `/hub/api/user`. In production, Hub login cookies are scoped to `/hub/` and are not available on `/services/nblaunch/oauth_callback`.

### 8. Shared-home deployment alignment
The nblaunch pod must write into the same shared storage namespace used by single-user pods.

The deployment must use:
- shared-home PVC: `home-nfs`
- mount path in nblaunch pod: `/home`
- `NBLAUNCH_NOTEBOOK_BASE_DIR=/home`

With Hub-provided `home_subpath=users/<normalized-user>`, the nblaunch write target must therefore resolve to:
- `/home/users/<normalized-user>/nbgallery/<notebook>.ipynb`

This is the nblaunch-visible path corresponding to the single-user pod’s `/home/jovyan/nbgallery/<notebook>.ipynb`, where `/home/jovyan` is backed by NFS export `/users/<normalized-user>`.

Do not use:
- PVC `jupyterhub-user-homes`
- mount path `/srv/jupyterhub/users`
- base dir `/srv/jupyterhub/users`

for this production layout.

## Tasks for the AI
1. Update service routing and callback handling in `services/nblaunch/src/nblaunch/app.py` to support the production prefixed service paths.
2. Load and use real gallery configuration from `services/nblaunch/src/nblaunch/config.py`.
3. Correct Hub endpoint derivation so the app can build `/api/user`, `/api/oauth2/token`, and related Hub URLs from the configured base.
4. Implement OAuth callback code exchange and token-authenticated user resolution in `services/nblaunch/src/nblaunch/app.py`.
5. Ensure launch-time user resolution rejects the legacy placeholder and consistently prefers the real Hub identity.
6. Keep Hub-owned home-subpath logic and improve the pre-spawn hook mount matching as needed so the intended home mount is mutated reliably.
7. Update `services/nblaunch/k8s/deployment.yaml` so the nblaunch pod:
   - can reach the Hub
   - mounts `home-nfs`
   - writes under `/home`
8. Add or update tests covering:
   - prefixed route behavior
   - callback path alignment
   - callback success via OAuth code exchange
   - callback failure when user resolution fails
   - launch ignoring the placeholder username
   - launch preferring the real Hub user
   - launch using the Hub-owned home-subpath mapping
   - deployment/config expectations for the corrected base dir and PVC

## Expected outputs
- nblaunch serves the correct prefixed routes in production.
- OAuth callback succeeds using code exchange and real user resolution.
- launch flow calls the home-subpath endpoint with the real Hub username.
- notebooks are written into the correct shared home location.
- deployment assets reflect the real NFS-backed storage topology.
- integration tests protect the working auth and routing behavior.

## Acceptance criteria
- Unauthenticated access to `/services/nblaunch/launch` redirects into JupyterHub OAuth with callback URI `/services/nblaunch/oauth_callback`.
- `/services/nblaunch/oauth_callback` exchanges the OAuth code at `/hub/api/oauth2/token`.
- The callback resolves the authenticated Hub user via token-authenticated `/hub/api/user`.
- The launch flow never uses `oauth-authenticated-user` as the effective username.
- The launch flow calls `/services/nblaunch/home-subpath/<real-user>`.
- The final notebook write path in the nblaunch pod resolves under `/home/users/<normalized-user>/nbgallery/...`.
- The notebook is visible in JupyterLab under `/home/jovyan/nbgallery/...`.
- The deployment uses:
  - `NBLAUNCH_HUB_API_URL=http://hub:8081`
  - `NBLAUNCH_NOTEBOOK_BASE_DIR=/home`
  - PVC `home-nfs`
  - mount path `/home`
  - `hub.jupyter.org/network-access-hub: "true"`

## Common failure modes / things to watch
- callback path mismatch between Hub config and service route registration
- using `NBLAUNCH_HUB_API_URL` with a pre-appended `/hub/api` suffix
- trying to resolve callback users from `/services/...` browser cookies instead of exchanging the OAuth code
- accepting `oauth-authenticated-user` as a real username
- writing notebooks under a base dir that is not the live NFS root seen by nblaunch
- assuming the single-user pod and nblaunch pod see the shared storage through the same mount path
- mutating the wrong volume mount in the pre-spawn hook

## Suggested commit boundary
1. Service prefix, gallery config, and Hub API base corrections
2. Hub access and home-subpath hook/API corrections
3. Real-user resolution and placeholder rejection
4. OAuth callback code exchange and regression tests
5. Deployment shared-home alignment

## Handoff to human
Verify in the live cluster that:
- Hub logs show successful service OAuth authorize and callback flow
- callback performs `POST /hub/api/oauth2/token` followed by token-authenticated `GET /hub/api/user`
- nblaunch resolves the real username, not `oauth-authenticated-user`
- nblaunch calls `/services/nblaunch/home-subpath/<real-user>`
- the notebook is written under `/home/users/<normalized-user>/nbgallery/...` in the nblaunch pod
- the same notebook appears under `/home/jovyan/nbgallery/...` in the user pod
- operations manifests and checked-in manifests agree on the image, Hub API URL, PVC, and mount path
