#!/usr/bin/env bash
# One-command local setup for fixit-backend (macOS / Linux / Git Bash).
#
#   ./scripts/bootstrap.sh          # create .env, start Postgres + API, wait until healthy
#   ./scripts/bootstrap.sh --seed   # same, then load dev seed data
#
# Safe to run again: an existing .env is kept (only an empty JWT_SECRET_KEY gets filled in).
set -euo pipefail

cd "$(dirname "$0")/.."

SEED=0
for arg in "$@"; do
  case "$arg" in
    --seed) SEED=1 ;;
    -h | --help)
      sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown option: $arg (use --help)" >&2
      exit 2
      ;;
  esac
done

step() { printf '\n==> %s\n' "$1"; }
fail() {
  printf '\nERROR: %s\n' "$1" >&2
  exit 1
}

new_secret() { od -An -tx1 -N32 /dev/urandom | tr -d ' \n'; }

step "Checking Docker"
command -v docker >/dev/null 2>&1 ||
  fail "Docker is not installed. Install Docker Desktop: https://www.docker.com/products/docker-desktop/"
docker info >/dev/null 2>&1 || fail "Docker is not running. Start Docker Desktop and run this script again."
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 ('docker compose') is required."

step "Preparing .env"
if [ -f .env ]; then
  echo ".env already exists, keeping it."
else
  cp .env.example .env
  echo "Created .env from .env.example."
fi
if ! grep -Eq '^JWT_SECRET_KEY=[^[:space:]]' .env; then
  secret="$(new_secret)"
  if grep -Eq '^JWT_SECRET_KEY=' .env; then
    tmp="$(mktemp)"
    sed "s/^JWT_SECRET_KEY=.*/JWT_SECRET_KEY=${secret}/" .env >"$tmp" && cat "$tmp" >.env
    rm -f "$tmp"
  else
    printf '\nJWT_SECRET_KEY=%s\n' "$secret" >>.env
  fi
  echo "Generated a new JWT_SECRET_KEY in .env."
fi

step "Building and starting Postgres + backend (first run can take a few minutes)"
if ! docker compose up --build -d; then
  fail "docker compose failed. If it says 'port is already allocated', set POSTGRES_PORT in .env
(e.g. 5433) or stop whatever uses port 8000. See README > Troubleshooting."
fi

step "Waiting for the API to become healthy"
healthy=0
for _ in $(seq 1 60); do
  if docker compose exec -T backend python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)" \
    >/dev/null 2>&1; then
    healthy=1
    break
  fi
  sleep 2
done
if [ "$healthy" -ne 1 ]; then
  docker compose logs --tail 40 backend || true
  fail "The API did not become healthy within 2 minutes. See the backend logs above."
fi

if [ "$SEED" -eq 1 ]; then
  step "Loading dev seed data"
  docker compose exec -T backend python -m app.seed
fi

cat <<'MSG'

FixIt backend is running.
  API:          http://localhost:8000
  Health check: http://localhost:8000/health
  API docs:     http://localhost:8000/docs

  Logs:  docker compose logs -f backend
  Stop:  docker compose down        (add -v to also delete the database)
MSG
