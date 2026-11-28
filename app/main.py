from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.exception_handlers import register_exception_handlers
from app.routers import (
    auth,
    categories,
    chats,
    health,
    issues,
    masters,
    search,
    service_centers,
    uploads,
    users,
    volunteer_requests,
)
from app.schemas.errors import ERROR_RESPONSES
from app.schemas.health import RootResponse

app = FastAPI(title=settings.app_name, responses=ERROR_RESPONSES)
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(categories.router)
app.include_router(chats.router)
app.include_router(issues.router)
app.include_router(masters.router)
app.include_router(search.router)
app.include_router(service_centers.router)
app.include_router(users.router)
app.include_router(volunteer_requests.router)
app.include_router(uploads.router)

# Uploaded files are served from MEDIA_ROOT (local storage).
# Uploaded files are served from MEDIA_ROOT (local storage).
# Only avatars are public static files. Chat photos are private: GET /uploads/{id}/file.
avatars_dir = Path(settings.media_root) / "avatars"
avatars_dir.mkdir(parents=True, exist_ok=True)
app.mount(f"{settings.media_url}/avatars", StaticFiles(directory=avatars_dir), name="avatars")


@app.middleware("http")
async def no_content_sniffing(request: Request, call_next):
    """Browsers must trust our Content-Type and never guess, e.g. treat an image as HTML."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/", response_model=RootResponse)
def root() -> RootResponse:
    return RootResponse(name=settings.app_name)
