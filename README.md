# fixit-backend
FastAPI backend

## Running locally

### Prerequisites

- [Python 3.12](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)

### 1. Install dependencies

```bash
uv sync
```

This creates `.venv` and installs all dependencies (including dev tools) from `uv.lock`.

### 2. Configure environment

Copy the example env file:

```bash
cp .env.example .env

# Windows (PowerShell)
Copy-Item .env.example .env
```

The defaults work with the local Postgres container below.

### 3. Start Postgres

```bash
docker run --name fixit-db -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=fixit -p 5432:5432 -d postgres:17
```

Next time, just run `docker start fixit-db`.

### 4. Run the API

```bash
uv run uvicorn app.main:app --reload
```

- API: http://localhost:8000
- Health check: http://localhost:8000/health
- Interactive docs: http://localhost:8000/docs

### Tests and linting

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
```

### Running with Docker

```bash
docker build -t fixit-backend .
docker run --rm -p 8000:8000 -e DATABASE_URL=postgresql+psycopg://postgres:postgres@host.docker.internal:5432/fixit fixit-backend
```

### Running with Docker Compose (DB + backend)

One command starts Postgres, applies migrations and runs the API with auto-reload:

```bash
cp .env.example .env   # once
docker compose up --build
```

- API: http://localhost:8000, health check: http://localhost:8000/health
- Postgres: `localhost:${POSTGRES_PORT}` (default `5432`). If the port is taken, set
  `POSTGRES_PORT` (and the port in `DATABASE_URL`) in `.env`.
- Data is kept in the `db_data` volume. Wipe it with `docker compose down -v`.

### Database migrations (Alembic)

Migrations live in `migrations/versions`. With compose they are applied automatically on start.

```bash
# after changing models in app/models: generate a migration, review it, then apply
docker compose exec backend alembic revision --autogenerate -m "short description"
docker compose exec backend alembic upgrade head

# check that models and migrations are in sync
docker compose exec backend alembic check
```

Without Docker: `uv run alembic upgrade head` (uses `DATABASE_URL` from `.env`).

### Dev seed data

```bash
docker compose exec backend python -m app.seed
```

### Environment variables

| Variable       | Description                          | Default                                                       |
|----------------|--------------------------------------|---------------------------------------------------------------|
| `APP_NAME`     | API title shown in docs              | `FixIt API`                                                   |
| `DATABASE_URL` | Postgres connection string           | `postgresql+psycopg://postgres:postgres@localhost:5432/fixit` |
| `CORS_ORIGINS` | Allowed origins as a JSON list       | `["http://localhost:8081"]`                                   |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Postgres container credentials (compose) | `postgres` / `postgres` / `fixit` |
| `POSTGRES_PORT` | Host port of the Postgres container (compose) | `5432` |

## CI/CD secrets

Set these under Settings → Secrets and variables → Actions. Until real values exist, they hold placeholders.

| Secret | Used for |
| --- | --- |
| `REGISTRY_URL` | Container registry host and namespace, e.g. `ghcr.io/fixit-garage` |
| `REGISTRY_USERNAME` | Registry login user (not needed for GHCR, which uses `GITHUB_TOKEN`) |
| `REGISTRY_PASSWORD` | Registry password or access token (not needed for GHCR) |

## Deployment (TBD)

The backend deploy target is not decided yet.
A placeholder workflow lives in `.github/workflows/deploy.yml` and runs manually only.
The Docker image is built and pushed to GHCR by `.github/workflows/docker.yml` on merge to `main`.
