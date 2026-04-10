from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import init_db
from app.routers import ask, events, items, search, system


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Refrigerator Event Stream",
    description="Manage your refrigerator items with expiration tracking and semantic search",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(system.router)
app.include_router(items.router)
app.include_router(events.router)
app.include_router(search.router)
app.include_router(ask.router)
