import asyncio
from unittest.mock import AsyncMock, MagicMock

from fastapi import WebSocketDisconnect

import backend.api.routes as routes
from backend.api import websocket as websocket_module
from backend.core.application import Application
from backend.core.event_bus import EventBus


def test_run_boss_publishes_timeout_failure(monkeypatch):
    async def run_test():
        event_bus = EventBus()
        monkeypatch.setattr(routes.application, "event_bus", event_bus)
        monkeypatch.setenv("LOCAL_AI_OFFICE_REQUEST_TIMEOUT", "0.01")

        async def slow_boss(message):
            await asyncio.sleep(1)
            return "too late"

        monkeypatch.setattr(routes.application.boss, "run", slow_boss)

        await routes.run_boss(
            message="Build a slow application",
            request_id="timeout-123",
        )

        events = event_bus.get_all_events()
        event_types = [event.event_type for event in events]

        assert "request_started" in event_types
        assert "request_failed" in event_types
        assert "request_completed" not in event_types

        failed_event = next(
            event
            for event in events
            if event.event_type == "request_failed"
        )

        assert failed_event.data["request_id"] == "timeout-123"
        assert "timed out after" in failed_event.data["error"]

    asyncio.run(run_test())


def test_websocket_timeout_sends_boss_response(monkeypatch):
    async def run_test():
        from backend.core.application import application

        event_bus = EventBus()
        monkeypatch.setattr(application, "event_bus", event_bus)
        monkeypatch.setenv("LOCAL_AI_OFFICE_REQUEST_TIMEOUT", "0.01")

        async def slow_boss(message):
            await asyncio.sleep(1)
            return "too late"

        monkeypatch.setattr(application.boss, "run", slow_boss)

        websocket = MagicMock()
        websocket.accept = AsyncMock()
        websocket.receive_text = AsyncMock(
            side_effect=[
                "Build a slow application",
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
        failed_event = next(
            event
            for event in events
            if event.event_type == "request_failed"
        )

        assert "timed out after" in failed_event.data["error"]

        sent_events = [
            call.args[0]
            for call in websocket.send_json.call_args_list
        ]
        boss_response = next(
            event
            for event in sent_events
            if event["event_type"] == "boss_response"
        )

        assert boss_response["data"]["error"] is True
        assert "timed out after" in boss_response["data"]["message"]

    asyncio.run(run_test())


def test_shutdown_cancels_tracked_tasks():
    async def run_test():
        application = object.__new__(Application)
        application.background_tasks = set()

        async def pending():
            await asyncio.sleep(30)

        task = application.track_task(pending(), name="pending-test")
        assert task in application.background_tasks

        await application.shutdown()

        assert task.cancelled()
        assert application.background_tasks == set()

    asyncio.run(run_test())
