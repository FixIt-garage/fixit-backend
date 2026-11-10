from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.exception_handlers import register_exception_handlers
from app.routers import auth, categories, health, issues
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


@app.get("/", response_model=RootResponse)
def root() -> RootResponse:
    return RootResponse(name=settings.app_name)