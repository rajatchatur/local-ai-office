from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.routes import router
from backend.api.websocket import websocket_endpoint

from backend.core.application import application


app = FastAPI(
    title="Local AI Office",
    description="Local multi-agent AI office",
    version="1.0.0",
)


app.include_router(
    router
)


app.mount(
    "/office",
    StaticFiles(
        directory="frontend/office"
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