from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.exception_handlers import register_exception_handlers
from app.routers import (
    auth,
    categories,
    health,
    issues,
    masters,
    service_centers,
    uploads,
    users,
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
app.include_router(issues.router)
app.include_router(masters.router)
app.include_router(service_centers.router)
app.include_router(users.router)
app.include_router(uploads.router)

# Uploaded files are served from MEDIA_ROOT (local storage).
Path(settings.media_root).mkdir(parents=True, exist_ok=True)
app.mount(settings.media_url, StaticFiles(directory=settings.media_root), name="media")


@app.get("/", response_model=RootResponse)
def root() -> RootResponse:
    return RootResponse(name=settings.app_name)