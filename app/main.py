from fastapi import FastAPI

from app.config import settings
from app.routers import health

app = FastAPI(title=settings.app_name)

app.include_router(health.router)


@app.get("/")
def root():
    return {"name": settings.app_name}