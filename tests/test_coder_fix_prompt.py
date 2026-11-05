import asyncio
import json

from backend.agents.coder import CoderAgent


def test_fix_project_prompt_includes_failure_and_missing_import_guidance():
    async def run_test():
        agent = object.__new__(CoderAgent)
        captured = {}

        class MockLLM:
            async def generate(self, **kwargs):
                captured.update(kwargs)
                return json.dumps({
                    "file": "test_main.py",
                    "content": "from main import add\n",
                })

        agent.llm = MockLLM()
        agent.inspect_project = lambda project_name: {
            f"{project_name}/main.py": (
                "def add(a, b):\n"
                "    return a + b\n"
            ),
            f"{project_name}/test_main.py": (
                "def test_add():\n"
                "    assert add(2, 3) == 5\n"
            ),
        }

        failure = {
            "return_code": 1,
            "stdout": "",
            "stderr": (
                "NameError: name 'add' is not defined\n"
                "test_main.py:2"
            ),
            "test_result": {
                "status": "failed",
                "return_code": 1,
                "stderr": "NameError: name 'add' is not defined",
            },
        }

        fix = await agent.fix_project("PromptRegressionTest", failure)

        assert fix["file"] == "test_main.py"
        assert "NameError: name 'add' is not defined" in captured["prompt"]
        assert "missing imports" in captured["prompt"]
        assert "correct import from the application module" in captured["prompt"]
        assert captured["format"] == "json"

    asyncio.run(run_test())
