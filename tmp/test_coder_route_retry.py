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
            print("TEST: Returning broken GET-only route")
            return make_response("GET")

        print("TEST: Returning corrected POST route")
        return make_response("POST")


async def main():
    agent = object.__new__(CoderAgent)
    agent.llm = MockLLM()
    agent.set_status = lambda *args, **kwargs: None

    # Prevent writing or running any real project files.
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

    assert agent.llm.calls == 2, (
        f"Expected 2 model calls, got {agent.llm.calls}"
    )

    print("\nPASS: Broken route triggered validation retry")
    print("PASS: Corrected response passed validation")
    print("PASS: No real project files were written")
    print(f"Model calls: {agent.llm.calls}")
    print("Result:", result)


asyncio.run(main())


