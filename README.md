# nblaunch
=======
# nblaunch

Minimal scaffold for the nblaunch service.

## Local Run

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

## Run Tests

From `services/nblaunch`:

```bash
pytest tests/unit/test_config.py
pytest tests/integration/test_routes.py
pytest tests
```

## Docker

Build from `services/nblaunch`:

```bash
docker build -t nblaunch:dev .
```

Run:

```bash
docker run --rm -p 8000:8000 \
  -e NBLAUNCH_HMAC_SECRET=example \
  -e NBLAUNCH_SERVICE_TOKEN=example \
  -e NBLAUNCH_HUB_API_URL=http://hub:8081/hub/api \
  -e NBLAUNCH_NOTEBOOK_BASE_DIR=/tmp/notebooks \
  nblaunch:dev
```
