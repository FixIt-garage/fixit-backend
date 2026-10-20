from fastapi import FastAPI

from app.config import settings

app = FastAPI(title=settings.app_name)


@app.get("/")
def root():
    return {"name": settings.app_name}