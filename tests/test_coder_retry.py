import asyncio
import json

from backend.agents.coder import CoderAgent

def make_response(method):
    project = {
        "project_name": "RouteRetryTest",
        "summary": "Test Flask route validation and retry",
        "files": [
            {
                "path": "main.py",
                "content": (
                    "from flask import Flask\n"
                    "app = Flask(__name__)\n"
                    f"@app.route('/save', methods=['{method}'])\n"
                    "def save():\n"
                    "    return 'Saved'\n"
                ),
            },
            {
                "path": "templates/index.html",
                "content": (
                    '<form action="/save" method="post">'
                    '<button type="submit">Save</button></form>'
                ),
            },
            {
                "path": "requirements.txt",
                "content": "Flask\n",
            },
        ],
    }
    return json.dumps(project)

class MockLLM:
    def __init__(self):
        self.calls = 0

    async def generate(self, **kwargs):
        self.calls += 1

        if self.calls == 1:
            return make_response("GET")

        return make_response("POST")

def test_broken_flask_route_triggers_retry():
    async def run_test():
        agent = object.__new__(CoderAgent)
        mock_llm = MockLLM()

        agent.llm = mock_llm
        agent.set_status = lambda *args, **kwargs: None

        # Prevent writes to the real workspace or execution of real files.
        agent.write_project_to_workspace = (
            lambda project: "/tmp/mock-route-retry"
        )
        agent.run_project = lambda path: {
            "return_code": 0,
            "stdout": "Mock execution succeeded",
            "stderr": "",
        }

        result = await agent.run(
            "Build a simple Flask app with a form that submits to /save."
        )

        assert mock_llm.calls == 2, (
            f"Expected 2 model calls, got {mock_llm.calls}"
        )
        assert result is not None

    asyncio.run(run_test())
