# fixit-backend
FastAPI backend

## Quick start

Requires only [Git](https://git-scm.com/) and [Docker Desktop](https://www.docker.com/products/docker-desktop/) (running).

```bash
git clone --branch develop https://github.com/FixIt-garage/fixit-backend.git
cd fixit-backend

# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1

# macOS / Linux
./scripts/bootstrap.sh
```

The script creates `.env` (with a generated `JWT_SECRET_KEY`), builds and starts Postgres and the API,
applies migrations and waits until http://localhost:8000/health is OK.
Add `-Seed` (PowerShell) or `--seed` (bash) to also load dev seed data.
It is safe to run again: an existing `.env` is kept, only an empty `JWT_SECRET_KEY` is filled in.
Use the `develop` branch: it is where the bootstrap scripts live until they reach `main`.

Stop everything with `docker compose down` (add `-v` to also delete the database).

### Troubleshooting

- **Docker is not running**: start Docker Desktop and wait for "Engine running", then run the script again.
- **`port is already allocated`**: port 5432 or 8000 is taken. For Postgres, set `POSTGRES_PORT=5433`
  in `.env` (and the port in `DATABASE_URL` if you run the API without Docker). For 8000, stop the
  other app or container that uses it (`docker ps`).
- **`running scripts is disabled on this system`**: start the script with
  `powershell -ExecutionPolicy Bypass -File ...` as shown above.
- **`Read timed out` while building**: the Python package download timed out. Run the script again.
- **The API does not become healthy**: check `docker compose logs backend`. A database created with
  other credentials needs `docker compose down -v` (this deletes local data).

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

Generate a secure JWT secret key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the generated value into `.env`, replacing the empty `JWT_SECRET_KEY`:

```env
JWT_SECRET_KEY=your-generated-secret-key
```

Use a different key for each environment. Never commit `.env` or share your secret key.

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
docker run --rm -p 8000:8000 \
  -e DATABASE_URL=postgresql+psycopg://postgres:postgres@host.docker.internal:5432/fixit \
  -e JWT_SECRET_KEY=your-generated-secret-key \
  fixit-backend
```

### Running with Docker Compose (DB + backend)

One command starts Postgres, applies migrations and runs the API with auto-reload:

```bash
cp .env.example .env
docker compose up --build
```
Generate a JWT secret key using the command from the Configure environment section and set it as `JWT_SECRET_KEY` in `.env` before starting the services.

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

| Variable                                              | Description                                                                   | Default                                                       |
|-------------------------------------------------------|-------------------------------------------------------------------------------|---------------------------------------------------------------|
| `APP_NAME`                                            | API title shown in docs                                                       | `FixIt API`                                                   |
| `DATABASE_URL`                                        | Postgres connection string                                                    | `postgresql+psycopg://postgres:postgres@localhost:5432/fixit` |
| `CORS_ORIGINS`                                        | Allowed origins as a JSON list                                                | `["http://localhost:8081"]`                                   |
| `JWT_SECRET_KEY`                                      | Secret key used to sign JWT tokens. Must be generated before starting the API | No default (required)                                                     |
| `JWT_ALGORITHM`                                       | Algorithm used to sign JWT tokens                                             | `HS256`                                                       |
| `ACCESS_TOKEN_EXPIRE_MINUTES`                         | Access token lifetime in minutes                                              | `15`                                                          |
| `REFRESH_TOKEN_EXPIRE_DAYS`                           | Refresh token lifetime in days                                                | `30`                                                          |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Postgres container credentials (compose)                                      | `postgres` / `postgres` / `fixit`                             |
| `POSTGRES_PORT`                                       | Host port of the Postgres container (compose)                                 | `5432`                                                        |
| `STORAGE_BACKEND`                                     | Where uploaded files are stored (only `local` for now)                        | `local`                                                       |
| `MEDIA_ROOT`                                          | Folder for uploaded files (local storage)                                     | `media`                                                       |
| `MEDIA_URL`                                           | URL prefix the public files (avatars) are served from                         | `/media`                                                      |
| `MAX_UPLOAD_SIZE_MB`                                  | Maximum upload size in MB                                                     | `5`                                                           |
| `MAX_IMAGE_PIXELS`                                    | Maximum image resolution (width x height), checked before decoding            | `40000000`                                                    |
| `AVATAR_SIZE_PX`                                      | Avatars are cropped to a square of this size                                  | `512`                                                         |

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


## Adding DTOs for a new endpoint

All request and response schemas live in `app/schemas/`, one module per domain (`issue.py`, `auth.py`, ...).

**Naming:** `XCreate` for POST bodies, `XUpdate` for PATCH bodies, `XRead` for responses.

**Base classes** (`app/schemas/base.py`):

- Request DTOs inherit `RequestSchema`: unknown fields are rejected with 422, strings are stripped.
- Response DTOs inherit `BaseSchema`: `from_attributes=True`, so routes can return ORM objects.

**Constraints:** use `Field(...)` for lengths and ranges, enums for fixed values, `EmailStr` for emails. In `XUpdate` make every field optional (`= None`) for partial updates.

**Every route declares `response_model`**, so only DTO fields are returned and documented.

**Lists use shared pagination:**

```python
@router.get("", response_model=Page[XRead])
def list_x(params: Annotated[PageParams, Depends()], ...):
    ...
```

Use `Depends()`, not `Query()`, for `PageParams`: with `Query()` the params break as soon as the route has other query parameters.

**Errors:** raise `HTTPException(status_code, "message")`. All errors are returned as `{"code", "message", "details"}`; validation errors list field paths in `details` (e.g. `body.email`, `query.limit`).zeZz

## Uploads (avatars and chat photos)

`POST /uploads` takes a multipart form with `kind` (`avatar` or `chat`) and `file`, and returns the file URL:

```bash
curl -X POST http://localhost:8000/uploads \
  -H "Authorization: Bearer <access token>" \
  -F kind=avatar -F file=@photo.jpg
```

- Allowed types: jpeg, png, heic. The type is checked from the file content, not its name (other files: 415).
- Limits: `MAX_UPLOAD_SIZE_MB` for the file and `MAX_IMAGE_PIXELS` for the resolution (both: 413).
- Images are re-encoded, so metadata (EXIF with the GPS location, ICC profiles) is removed. HEIC is stored as JPEG.
- Avatars are cropped to `AVATAR_SIZE_PX`, set as the user's `avatar_url` and served publicly from `MEDIA_URL/avatars/...`.
- Chat photos are private. Upload with `kind=chat`, then send the returned `url` (`/uploads/{id}/file`) as `photo_url` in a chat message. The file is returned only with a token, to the uploader and to the participants of a conversation where the uploader sent it (others get 404).  It is sent with `Cache-Control: no-store`, so devices do not keep a copy; the mobile app should also clear its own image cache on logout or account switch.
- All responses have `X-Content-Type-Options: nosniff`.
- Files are stored in `MEDIA_ROOT`. In Docker Compose they live in the `media_data` volume.
- S3-compatible storage is not implemented yet: add another class next to `LocalStorage` in `app/services/storage.py`.