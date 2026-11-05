from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from backend.api.routes import router
from backend.api.websocket import websocket_endpoint

from backend.core.application import application


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await application.shutdown()


app = FastAPI(
    title="Local AI Office",
    description="Local multi-agent AI office",
    version="1.0.0",
    lifespan=lifespan,
)


app.include_router(
    router
)


app.mount(
    "/office",
    StaticFiles(
        directory=str(Path(__file__).resolve().parents[1] / "frontend" / "office")
    ),
    name="office",
)


app.websocket(
    "/ws"
)(
    websocket_endpoint
)


@app.get("/")
async def root():

    return {
        "application": "Local AI Office",
        "status": "running",
        "office": "/office/office.html",
        "websocket": "/ws",
    }