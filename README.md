# nblaunch
=======
# nblaunch

`nblaunch` validates signed launch URLs, resolves the authenticated user's notebook root through JupyterHub, fetches notebook content, writes it safely, and redirects the user into JupyterLab.

## Required inputs

Secrets:
- `NBLAUNCH_HMAC_SECRET`: shared secret for launch-link signing.
- `NBLAUNCH_SERVICE_TOKEN`: JupyterHub service token used for home-subpath lookup.

Non-secrets:
- `NBLAUNCH_HUB_API_URL`: Hub API base URL, for example `http://hub:8081/hub/api`.
- `NBLAUNCH_GALLERY_BASE_URL`: notebook-source site root, for example `https://gallery.example`.
- `NBLAUNCH_GALLERY_DOWNLOAD_PATH_TEMPLATE`: notebook download path template, default `/api/notebooks/{notebook_id}`.
- `NBLAUNCH_GALLERY_USER_AGENT`: user agent sent to the notebook source, default is a browser-like Chrome string.
- `NBLAUNCH_NOTEBOOK_BASE_DIR`: filesystem root containing per-user notebook homes.
- `NBLAUNCH_JUPYTERHUB_BASE_URL`: Hub base URL prefix, default `/`.

Runtime tuning:
- `NBLAUNCH_SIGNATURE_TTL_SECONDS`: launch-link validity window, default `300`.
- `NBLAUNCH_MAX_NOTEBOOK_BYTES`: max fetched notebook payload, default `10485760`.
- `NBLAUNCH_GALLERY_TIMEOUT_SECONDS`: notebook fetch timeout, default `10`.
- `NBLAUNCH_HTTP_TIMEOUT_SECONDS`: Hub API timeout, default `10`.
- `NBLAUNCH_LOG_LEVEL`: log level, default `INFO`.

## Local run

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start the service from `services/nblaunch`:

```bash
PYTHONPATH=src python -m nblaunch.main
```

Service listens on `http://127.0.0.1:8000` by default.

## Image build

Build from `services/nblaunch`:

```bash
docker build -t nblaunch:dev .
```

Example local container run:

```bash
docker run --rm -p 8000:8000 \
  -e NBLAUNCH_HMAC_SECRET=example \
  -e NBLAUNCH_SERVICE_TOKEN=example \
  -e NBLAUNCH_HUB_API_URL=http://hub:8081/hub/api \
  -e NBLAUNCH_GALLERY_BASE_URL=https://gallery.example \
  -e NBLAUNCH_GALLERY_DOWNLOAD_PATH_TEMPLATE='/notebooks/{notebook_id}/download?clickstream=false' \
  -e NBLAUNCH_GALLERY_USER_AGENT='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36' \
  -e NBLAUNCH_NOTEBOOK_BASE_DIR=/srv/jupyterhub/users \
  -e NBLAUNCH_JUPYTERHUB_BASE_URL=/hub \
  nblaunch:dev
```

## Kubernetes rollout

Stage 07 deployment assets live under `services/nblaunch/k8s/`:
- `services/nblaunch/k8s/deployment.yaml`
- `services/nblaunch/k8s/service.yaml`
- `services/nblaunch/k8s/secret.example.yaml`

Recommended rollout sequence:
1. Build and publish the image tag you intend to deploy.
2. Copy `services/nblaunch/k8s/secret.example.yaml` to your deployment system and replace placeholder values.
3. Update `services/nblaunch/k8s/deployment.yaml` with the real image tag, real `NBLAUNCH_GALLERY_BASE_URL`, real `NBLAUNCH_GALLERY_DOWNLOAD_PATH_TEMPLATE`, real `NBLAUNCH_GALLERY_USER_AGENT` if needed, and any cluster-specific PVC name.
4. Roll out the Hub-side configuration with `helm upgrade --install ... --values jupyterhub/values-nblaunch.yaml` and your existing secret values.
5. Apply the `nblaunch` Secret, Deployment, and Service.
6. Wait for the Deployment to become ready before routing user traffic.

Verification after rollout:
1. `kubectl get deploy,svc,secret -n <namespace> | grep nblaunch`
2. `kubectl rollout status deploy/nblaunch -n <namespace>`
3. `kubectl logs deploy/nblaunch -n <namespace> --tail=100`
4. Port-forward or curl `/healthz`.
5. Generate a signed launch URL with `services/nblaunch/scripts/generate_nblaunch_url.sh` and validate the expected redirect behavior in staging.

Rollback:
1. `kubectl rollout undo deploy/nblaunch -n <namespace>`
2. Revert any paired JupyterHub config change if the failure is in service registration or extraConfig behavior.
3. Verify `/healthz`, OAuth redirect behavior, and notebook write-path behavior again before reopening traffic.

## Signed URL generation

Use `services/nblaunch/scripts/generate_nblaunch_url.sh` to generate a signed launch URL:

```bash
NBLAUNCH_HMAC_SECRET=replace-me \
./scripts/generate_nblaunch_url.sh \
  https://hub.example/services/nblaunch \
  gallery/notebook
```

The script prints a complete `/launch?...` URL with a fresh timestamp and HMAC signature.

## Validation workflow

Always-on tests:

```bash
pytest tests
pytest tests/smoke/test_nblaunch_config_render.py
```

Environment-dependent e2e validation:

```bash
pytest tests/e2e/test_nblaunch_open_in_hub.py
```

E2E prerequisites are environment variables documented in `tests/e2e/test_nblaunch_open_in_hub.py`. The test is skipped unless those inputs are present.

## Troubleshooting

Common failure modes:
- `401 invalid_signature`: HMAC secret mismatch or stale timestamp.
- `302` back to Hub OAuth unexpectedly: missing authenticated service context or cookie/session mismatch.
- `404 missing_user_home_mapping`: Hub home-subpath API returned no mapping for the user.
- `502 hub_home_lookup_failed`: Hub API route, authorization, or returned subpath is invalid.
- `502 gallery_fetch_failed`: upstream notebook source unavailable or returned the wrong content type.
- `500 storage_write_failed`: notebook base directory, mount, or permissions are wrong.

Practical checks:
1. Confirm `NBLAUNCH_HUB_API_URL` matches the real Hub API path.
2. Confirm `NBLAUNCH_GALLERY_BASE_URL`, `NBLAUNCH_GALLERY_DOWNLOAD_PATH_TEMPLATE`, and `NBLAUNCH_GALLERY_USER_AGENT` together resolve to a real notebook download endpoint reachable from the `nblaunch` pod.
3. Confirm the service token in Kubernetes matches the JupyterHub service registration.
4. Confirm the mounted notebook root matches the Stage 06 home-subpath algorithm and spawn-hook assumptions.
5. Re-run the smoke tests after any config edit.
6. Use the signed URL generator to reproduce the exact launch request being debugged.

## Hardening notes

- Keep `NBLAUNCH_HMAC_SECRET` and `NBLAUNCH_SERVICE_TOKEN` in Secret storage only.
- Rotate the HMAC secret and service token independently; update both the service and any launch-link generator before switching traffic.
- Keep `NBLAUNCH_SIGNATURE_TTL_SECONDS` short enough to limit replay, but long enough for realistic email/chat click latency.
- Keep `NBLAUNCH_MAX_NOTEBOOK_BYTES` conservative; large payloads raise disk and latency risk.
- Tune Hub and gallery timeouts together to avoid long-hanging requests during outages.
- The current Stage 05/06 implementation uses simple service cookies for local auth-flow continuity; production rollout should verify that this is acceptable in the target environment or replace it with the intended managed Hub session mechanism before broad rollout.
