import asyncio

import backend.api.routes as routes
from backend.core.event_bus import EventBus


def test_run_boss_publishes_request_failed_without_completing(monkeypatch):
    async def run_test():
        event_bus = EventBus()
        monkeypatch.setattr(routes.application, "event_bus", event_bus)

        async def fail_boss(message):
            raise RuntimeError("Simulated Boss worker failure")

        async def unexpected_artifact_persistence(request_id, coder_result):
            raise AssertionError(
                "Artifact persistence must not run after Boss failure"
            )

        monkeypatch.setattr(routes.application.boss, "run", fail_boss)
        monkeypatch.setattr(
            routes,
            "persist_coder_artifact",
            unexpected_artifact_persistence,
        )

        await routes.run_boss(
            message="Build a test application",
            request_id="test-failure-123",
        )

        events = event_bus.get_all_events()
        event_types = [event.event_type for event in events]

        assert "request_started" in event_types
        assert "request_failed" in event_types
        assert "request_completed" not in event_types

        failed_event = next(
            event for event in events
            if event.event_type == "request_failed"
        )

        assert failed_event.data["request_id"] == "test-failure-123"
        assert "Simulated Boss worker failure" in failed_event.data["error"]

    asyncio.run(run_test())
