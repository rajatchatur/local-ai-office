from backend.core.message_bus import AgentMessage
from backend.api.websocket import websocket_manager


def handle_agent_message(
    message: AgentMessage,
):

    payload = {

        "event_type": "message_sent",

        "agent": message.sender,

        "data": {

            "sender": message.sender,

            "receiver": message.receiver,

            "content": message.content,

            "created_at":
                message.created_at.isoformat(),

        },
    }


    try:

        from backend.core.application import application

        application.track_task(
            websocket_manager.broadcast(
                payload
            ),
            name="message_bridge_broadcast",
        )

    except RuntimeError:

        print(
            "MESSAGE BRIDGE: "
            "No running event loop."
        )