import asyncio

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

        loop = asyncio.get_running_loop()

        loop.create_task(
            websocket_manager.broadcast(
                payload
            )
        )

    except RuntimeError:

        print(
            "MESSAGE BRIDGE: "
            "No running event loop."
        )