import asyncio
from unittest.mock import AsyncMock, MagicMock

from backend.core.application import application
from backend.core.event_bus import EventBus
from backend.api import websocket as websocket_module


def test_websocket_boss_failure_publishes_request_failed(monkeypatch):
    async def run_test():
        event_bus = EventBus()
        monkeypatch.setattr(application, "event_bus", event_bus)

        async def fail_boss(message):
            raise RuntimeError("Simulated WebSocket worker failure")

        monkeypatch.setattr(application.boss, "run", fail_boss)

        websocket = MagicMock()
        websocket.accept = AsyncMock()
        from fastapi import WebSocketDisconnect

        websocket.receive_text = AsyncMock(
            side_effect=[
                "Build a test application",
                WebSocketDisconnect(),
            ]
        )
        websocket.send_json = AsyncMock()

        monkeypatch.setattr(
            websocket_module.websocket_manager,
            "connect",
            AsyncMock(),
        )
        monkeypatch.setattr(
            websocket_module.websocket_manager,
            "broadcast",
            AsyncMock(),
        )
        monkeypatch.setattr(
            websocket_module.websocket_manager,
            "disconnect",
            MagicMock(),
        )

        await websocket_module.websocket_endpoint(websocket)

        events = event_bus.get_all_events()
        event_types = [event.event_type for event in events]

        assert "request_started" in event_types
        assert "request_failed" in event_types
        assert "request_completed" not in event_types

        failed_event = next(
            event for event in events
            if event.event_type == "request_failed"
        )
        assert failed_event.data["request_id"]
        assert "Simulated WebSocket worker failure" in failed_event.data["error"]

        sent_events = [
            call.args[0]["event_type"]
            for call in websocket.send_json.call_args_list
        ]
        assert "user_request" in sent_events
        assert "boss_response" not in sent_events

    asyncio.run(run_test())
