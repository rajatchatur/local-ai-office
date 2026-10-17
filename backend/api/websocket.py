from fastapi import WebSocket, WebSocketDisconnect
import uuid
from backend.api.websocket_manager import WebSocketManager
from backend.agents.boss_agent import _coder_result_context
# from backend.core.application import application


websocket_manager = WebSocketManager()


async def websocket_endpoint(
    websocket: WebSocket,
):
    await websocket_manager.connect(websocket)

    from backend.core.application import application

    await websocket_manager.broadcast(
        {
            "event_type": "connection",
            "agent": "system",
            "data": {"message": "Connected to Local AI Office"},
        }
    )

    try:
        while True:
            request_id = None

            try:
                message = await websocket.receive_text()
                print(f"\nWEBSOCKET RECEIVED: {message}")
                request_id = str(uuid.uuid4())

                application.event_bus.publish(
                    event_type="request_started",
                    agent="boss",
                    data={"request_id": request_id, "message": message},
                )

                await websocket.send_json(
                    {
                        "event_type": "user_request",
                        "agent": "user",
                        "data": {"message": message},
                    }
                )

                _coder_result_context.set(None)
                result = await application.boss.run(message)

                from backend.api.routes import persist_coder_artifact

                coder_result = _coder_result_context.get()
                artifact_input = (
                    coder_result if coder_result is not None else result
                )
                artifact = await persist_coder_artifact(
                    request_id, artifact_input
                )

                application.event_bus.publish(
                    event_type="request_completed",
                    agent="boss",
                    data={
                        "request_id": request_id,
                        "response": result,
                        "artifact": artifact,
                    },
                )

                await websocket.send_json(
                    {
                        "event_type": "boss_response",
                        "agent": "boss",
                        "data": {"message": result},
                    }
                )

            except WebSocketDisconnect:
                raise

            except Exception as exc:
                if request_id is not None:
                    application.event_bus.publish(
                        event_type="request_failed",
                        agent="boss",
                        data={
                            "request_id": request_id,
                            "error": str(exc),
                        },
                    )

                print(
                    f"\nWEBSOCKET REQUEST FAILED: "
                    f"{type(exc).__name__}: {exc}"
                )

    except WebSocketDisconnect:
        print("\nWEBSOCKET: Client disconnected normally.")

    finally:
        websocket_manager.disconnect(websocket)
