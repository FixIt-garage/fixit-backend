from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    auth,
    categories,
    chats,
    health,
    issues,
    masters,
    search,
    service_centers,
    users,
    volunteer_requests,
)

app = FastAPI(title=settings.app_name)

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


@app.get("/")
def root():
    return {"name": settings.app_name}
