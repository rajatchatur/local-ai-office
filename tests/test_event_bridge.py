import asyncio
from unittest.mock import AsyncMock

from backend.api import event_bridge
from backend.core.event_bus import EventBus


def test_request_failed_event_is_forwarded_to_websocket_broadcast(monkeypatch):
    async def run_test():
        broadcast = AsyncMock()
        monkeypatch.setattr(
            event_bridge.websocket_manager,
            "broadcast",
            broadcast,
        )

        event_bus = EventBus()
        event_bus.subscribe(event_bridge.handle_agent_event)

        request_id = "test-websocket-bridge-123"
        error_message = "Simulated Boss worker failure"

        event_bus.publish(
            event_type="request_failed",
            agent="boss",
            data={
                "request_id": request_id,
                "error": error_message,
            },
        )

        # handle_agent_event schedules the async broadcast.
        await asyncio.sleep(0)

        broadcast.assert_awaited_once()
        message = broadcast.await_args.args[0]

        assert message["event_type"] == "request_failed"
        assert message["agent"] == "boss"
        assert message["data"]["request_id"] == request_id
        assert message["data"]["error"] == error_message
        assert "created_at" in message

    asyncio.run(run_test())
