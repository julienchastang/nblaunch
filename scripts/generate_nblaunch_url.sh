#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "usage: $0 <base-url> <notebook-id> [timestamp]" >&2
  exit 1
fi

if [[ -z "${NBLAUNCH_HMAC_SECRET:-}" ]]; then
  echo "NBLAUNCH_HMAC_SECRET must be set" >&2
  exit 1
fi

base_url="${1%/}"
notebook_id="$2"
timestamp="${3:-$(date +%s)}"

signature="$(
  NBLAUNCH_NOTEBOOK_ID="$notebook_id" \
  NBLAUNCH_TIMESTAMP="$timestamp" \
  python3 - <<'PY'
import hashlib
import hmac
import os

secret = os.environ["NBLAUNCH_HMAC_SECRET"].encode("utf-8")
notebook_id = os.environ["NBLAUNCH_NOTEBOOK_ID"]
timestamp = os.environ["NBLAUNCH_TIMESTAMP"]
message = f"nb={notebook_id}&ts={timestamp}".encode("utf-8")
print(hmac.new(secret, message, hashlib.sha256).hexdigest())
PY
)"

printf '%s/launch?nb=%s&ts=%s&sig=%s\n' \
  "$base_url" \
  "$notebook_id" \
  "$timestamp" \
  "$signature"
