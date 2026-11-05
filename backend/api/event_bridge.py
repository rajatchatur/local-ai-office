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

        from backend.core.application import application

        application.track_task(
            websocket_manager.broadcast(
                message
            ),
            name="event_bridge_broadcast",
        )

    except RuntimeError:

        print(
            "EVENT BRIDGE: No running event loop."
        )