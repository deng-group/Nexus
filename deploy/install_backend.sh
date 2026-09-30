#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/srv/mle-course-helper/backend}"
VENV_DIR="${VENV_DIR:-$APP_DIR/.venv}"

cd "$APP_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

# Install the exact versions pinned in uv.lock, plus gunicorn for the systemd service.
UV_PROJECT_ENVIRONMENT="$VENV_DIR" uv sync --frozen --extra deploy

"$VENV_DIR/bin/python" backend/scripts/query.py "What is convex hull?"

echo "Backend virtualenv is ready at $VENV_DIR"
echo "Next: copy deploy/env.example to /etc/mle-course-helper.env and install the systemd service."
