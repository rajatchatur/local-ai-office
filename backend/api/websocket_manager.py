from fastapi import WebSocket


class WebSocketManager:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        if websocket not in self.connections:
            self.connections.append(websocket)

        print(
            f"\nWEBSOCKET: Client connected "
            f"({len(self.connections)} clients)"
        )

    def disconnect(self, websocket: WebSocket):
        if websocket in self.connections:
            self.connections.remove(websocket)

        print(
            f"\nWEBSOCKET: Client disconnected "
            f"({len(self.connections)} clients)"
        )

    async def broadcast(self, message: dict):
        disconnected = []

        # Iterate over a snapshot because disconnect() modifies
        # the original connections list.
        for websocket in list(self.connections):
            try:
                await websocket.send_json(message)
            except Exception as exc:
                print(
                    "WEBSOCKET: Removing connection after send failure: "
                    f"{type(exc).__name__}: {exc}"
                )
                disconnected.append(websocket)

        for websocket in disconnected:
            self.disconnect(websocket)
