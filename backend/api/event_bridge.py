import asyncio

from backend.core.event_bus import AgentEvent
from backend.api.websocket import websocket_manager


def handle_agent_event(
    event: AgentEvent,
):

    message = {
        "event_type": event.event_type,
        "agent": event.agent,
        "data": event.data,
        "created_at": event.created_at.isoformat(),
    }

    try:

        loop = asyncio.get_running_loop()

        loop.create_task(
            websocket_manager.broadcast(
                message
            )
        )

    except RuntimeError:

        print(
            "EVENT BRIDGE: No running event loop."
        )