from fastapi.testclient import TestClient

from backend.agents.boss_agent import _coder_result_context
from backend.api import routes
from backend.core.application import application
from backend.main import app


CODER_JSON = '{"project_name": "CoderProject", "status": "success"}'


def test_websocket_persists_coder_result_not_boss_text(monkeypatch):
    """
    boss.run sets the coder result in a context variable. The WebSocket
    handler must see it, which fails if boss.run runs in a separate task
    (asyncio.wait_for on Python 3.11).
    """
    persisted = []

    async def fake_boss_run(message):
        _coder_result_context.set(CODER_JSON)
        return "Boss final text that is not the coder result"

    async def fake_persist(request_id, artifact_input):
        persisted.append(artifact_input)
        return {"artifact_id": "test-artifact"}

    monkeypatch.setattr(application.boss, "run", fake_boss_run)
    monkeypatch.setattr(routes, "persist_coder_artifact", fake_persist)

    with TestClient(app) as client:
        with client.websocket_connect("/ws") as websocket:
            assert websocket.receive_json()["event_type"] == "connection"

            websocket.send_text("Build a test application")

            while True:
                event = websocket.receive_json()
                if event.get("event_type") in ("boss_response", "request_failed"):
                    break

            assert event["event_type"] == "boss_response"

    assert persisted == [CODER_JSON]
