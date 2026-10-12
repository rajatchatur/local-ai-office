import asyncio
import json

import pytest

from backend.agents.coder import CoderAgent

def test_repair_rejects_path_outside_project():
    async def run_test():
        agent = object.__new__(CoderAgent)

        agent.set_status = lambda *args, **kwargs: None

        project = {
            "project_name": "RepairSafetyTest",
            "summary": "Test repair path safety",
            "files": [
                {
                    "path": "main.py",
                    "content": "print('hello')\n",
                }
            ],
        }

        agent.llm = None
        agent._build_prompt = lambda task: ""

        # Return a valid generated project on the initial LLM call.
        class MockLLM:
            async def generate(self, **kwargs):
                return json.dumps(project)

        agent.llm = MockLLM()

        agent._parse_project = lambda response: json.loads(response)
        agent._remove_stdlib_requirements = lambda project: False
        agent._validate_project = lambda project: None
        agent._validate_flask_consistency = lambda project: None
        agent._validate_flask_routes = lambda project: None

        agent.write_project_to_workspace = lambda project: "RepairSafetyTest"
        agent.run_project = lambda path: {
            "return_code": 1,
            "stdout": "",
            "stderr": "Simulated execution failure",
        }

        async def fake_fix_project(path, execution_result):
            return {
                "file": "../outside.py",
                "content": "print('unsafe')\n",
            }

        agent.fix_project = fake_fix_project

        agent.inspect_project = lambda path: {
            f"{path}/main.py": "print('hello')\n",
        }

        agent.edit_project_file = lambda *args, **kwargs: (
            pytest.fail("Unsafe repair must never be applied")
        )

        with pytest.raises(ValueError, match="unsafe repair path"):
            await agent.run("Build a simple Python application")

    asyncio.run(run_test())
