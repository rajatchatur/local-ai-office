import asyncio

import pytest

from backend.agents.coder import CoderAgent


def make_agent(files):
    agent = object.__new__(CoderAgent)
    agent.inspect_project = lambda name: {
        f"{name}/{path}": content
        for path, content in files.items()
    }
    return agent


def test_fix_project_rejects_invalid_json():
    async def run_test():
        agent = object.__new__(CoderAgent)

        class MockLLM:
            async def generate(self, **kwargs):
                return "not valid json"

        agent.llm = MockLLM()
        agent.inspect_project = lambda name: {
            f"{name}/main.py": "print('hello')\n"
        }

        with pytest.raises(ValueError, match="Invalid repair response JSON"):
            await agent.fix_project(
                "RepairValidation",
                {"return_code": 1, "stdout": "", "stderr": "failed"},
            )

    asyncio.run(run_test())


def test_repair_cannot_remove_existing_symbols():
    agent = make_agent({
        "main.py": (
            "def keep_me():\n"
            "    return 1\n"
        ),
    })

    with pytest.raises(ValueError, match="remove existing symbols"):
        agent._validate_repair(
            "RepairValidation",
            {
                "file": "main.py",
                "content": "print('symbol removed')\n",
            },
            "Update main.py",
        )


def test_explicit_symbol_removal_is_allowed():
    agent = make_agent({
        "main.py": (
            "def unused_helper():\n"
            "    return 1\n"
        ),
    })

    file_path, content = agent._validate_repair(
        "RepairValidation",
        {
            "file": "main.py",
            "content": "print('helper removed')\n",
        },
        "Remove the unused_helper function from main.py",
    )

    assert file_path == "main.py"
    assert content == "print('helper removed')\n"
