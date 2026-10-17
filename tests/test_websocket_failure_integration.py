from fastapi.testclient import TestClient

from backend.api import event_bridge
from backend.core.application import application
from backend.core.event_bus import EventBus
from backend.main import app


def test_connected_websocket_receives_request_failed(monkeypatch):
    event_bus = EventBus()
    event_bus.subscribe(event_bridge.handle_agent_event)

    monkeypatch.setattr(application, "event_bus", event_bus)

    async def fail_boss(message):
        raise RuntimeError("Simulated integration-test worker failure")

    monkeypatch.setattr(application.boss, "run", fail_boss)

    with TestClient(app) as client:
        with client.websocket_connect("/ws") as websocket:
            # Verify the real WebSocket connection is established.
            connected = websocket.receive_json()
            assert connected["event_type"] == "connection"

            websocket.send_text("Build a test application")

            received_events = []

            # Wait for the actual failure notification from the event bridge.
            # The endpoint intentionally stays connected after handling errors.
            while True:
                event = websocket.receive_json()
                received_events.append(event)

                if event.get("event_type") == "request_failed":
                    break

            failed_event = received_events[-1]

            assert failed_event["agent"] == "boss"
            assert failed_event["data"]["request_id"]
            assert (
                "Simulated integration-test worker failure"
                in failed_event["data"]["error"]
            )

            event_types = [
                event["event_type"] for event in received_events
            ]
            assert "user_request" in event_types
            assert "boss_response" not in event_types
            assert "request_completed" not in event_types

    published_events = event_bus.get_all_events()
    published_types = [
        event.event_type for event in published_events
    ]

    assert "request_started" in published_types
    assert "request_failed" in published_types
    assert "request_completed" not in published_types
