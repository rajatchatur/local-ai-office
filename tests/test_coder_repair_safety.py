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

def test_existing_project_repair_rejects_path_outside_project():
    async def run_test():
        agent = object.__new__(CoderAgent)

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

        def reject_edit(*args, **kwargs):
            pytest.fail("Unsafe repair must never be applied")

        agent.edit_project_file = reject_edit

        with pytest.raises(ValueError, match="unsafe repair path"):
            await agent.repair_existing_project("RepairSafetyTest")

    asyncio.run(run_test())


def test_existing_project_already_working_skips_repair():
    async def run_test():
        agent = object.__new__(CoderAgent)
        successful_execution = {
            "return_code": 0,
            "stdout": "Hello",
            "stderr": "",
        }
        agent.run_project = lambda path: successful_execution

        async def unexpected_fix(*args, **kwargs):
            pytest.fail("Working project must not trigger a repair")

        agent.fix_project = unexpected_fix

        result = await agent.repair_existing_project("RepairSafetyTest")

        assert result["status"] == "success"
        assert result["execution"] == successful_execution
        assert "fix" not in result

    asyncio.run(run_test())


def test_existing_project_repair_succeeds_after_rerun():
    async def run_test():
        agent = object.__new__(CoderAgent)
        executions = iter([
            {
                "return_code": 1,
                "stdout": "",
                "stderr": "Initial failure",
            },
            {
                "return_code": 0,
                "stdout": "Fixed",
                "stderr": "",
            },
        ])

        agent.run_project = lambda path: next(executions)
        agent.inspect_project = lambda path: {
            f"{path}/main.py": "print('broken')\n",
        }

        async def fake_fix_project(path, execution_result):
            assert execution_result["stderr"] == "Initial failure"
            return {
                "file": "main.py",
                "content": "print('fixed')\n",
            }

        agent.fix_project = fake_fix_project

        edits = []
        agent.edit_project_file = lambda *args: edits.append(args)

        result = await agent.repair_existing_project("RepairSafetyTest")

        assert result["status"] == "success"
        assert result["execution"]["return_code"] == 0
        assert len(edits) == 1
        assert edits[0][1] == "main.py"
        assert edits[0][2] == "print('fixed')\n"

    asyncio.run(run_test())


def test_existing_project_repair_reports_failure_if_rerun_fails():
    async def run_test():
        agent = object.__new__(CoderAgent)
        executions = iter([
            {
                "return_code": 1,
                "stdout": "",
                "stderr": "Initial failure",
            },
            {
                "return_code": 2,
                "stdout": "",
                "stderr": "Still broken",
            },
            {
                "return_code": 2,
                "stdout": "",
                "stderr": "Still broken",
            },
        ])

        agent.run_project = lambda path: next(executions)
        agent.inspect_project = lambda path: {
            f"{path}/main.py": "print('broken')\n",
        }

        async def fake_fix_project(path, execution_result):
            return {
                "file": "main.py",
                "content": "print('attempted fix')\n",
            }

        agent.fix_project = fake_fix_project
        agent.edit_project_file = lambda *args: None

        result = await agent.repair_existing_project("RepairSafetyTest")

        assert result["status"] == "failed"
        assert result["execution"]["return_code"] == 2
        assert result["execution"]["stderr"] == "Still broken"

    asyncio.run(run_test())

def test_existing_project_repair_rejects_malformed_fix():
    async def run_test():
        agent = object.__new__(CoderAgent)

        agent.run_project = lambda path: {
            "return_code": 1,
            "stdout": "",
            "stderr": "Simulated failure",
        }

        async def fake_fix_project(path, execution_result):
            return None

        agent.fix_project = fake_fix_project

        def reject_edit(*args, **kwargs):
            pytest.fail("Malformed repair must never be applied")

        agent.edit_project_file = reject_edit

        with pytest.raises(ValueError, match="Invalid repair response"):
            await agent.repair_existing_project("RepairSafetyTest")

    asyncio.run(run_test())
