import asyncio
import json
from types import SimpleNamespace

import backend.api.routes as routes
from backend.core.event_bus import EventBus


def test_persistence_uses_current_result_not_global_task_list(monkeypatch):
    async def run_test():
        request_id = "current-request-123"
        project = {
            "project_name": "CurrentProject",
            "status": "success",
            "files": [
                {"path": "main.py", "content": "print('current')"}
            ],
            "execution": {
                "return_code": 0,
                "stdout": "current",
                "stderr": "",
            },
        }

        captured = {}

        def create_project(**kwargs):
            captured.update(kwargs)
            return {
                "request_id": kwargs["request_id"],
                "project_name": kwargs["project_name"],
                "files": [{"path": "main.py", "size": 22}],
            }

        def forbidden_task_lookup():
            raise AssertionError(
                "Persistence must not search unrelated global tasks"
            )

        monkeypatch.setattr(
            routes.application,
            "task_manager",
            SimpleNamespace(get_all_tasks=forbidden_task_lookup),
        )
        monkeypatch.setattr(
            routes.application,
            "artifact_manager",
            SimpleNamespace(create_project=create_project),
        )

        event_bus = EventBus()
        monkeypatch.setattr(routes.application, "event_bus", event_bus)

        artifact = await routes.persist_coder_artifact(
            request_id,
            json.dumps(project),
        )

        assert captured["request_id"] == request_id
        assert captured["project_name"] == "CurrentProject"
        assert captured["files"] == project["files"]
        assert artifact["status"] == "success"
        assert artifact["execution_summary"]["return_code"] == 0

        events = event_bus.get_all_events()
        created = [
            event for event in events
            if event.event_type == "artifact_created"
        ]
        assert len(created) == 1
        assert created[0].data["request_id"] == request_id

    asyncio.run(run_test())


def test_persistence_ignores_non_project_response():
    async def run_test():
        artifact = await routes.persist_coder_artifact(
            "text-only-request",
            "This is a normal text response, not project JSON.",
        )
        assert artifact is None

    asyncio.run(run_test())
