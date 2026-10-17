import asyncio
import json

from backend.agents.coder import CoderAgent


def make_agent(execution_results):
    agent = object.__new__(CoderAgent)
    statuses = []
    edits = []

    project = {
        "project_name": "RepairResultTest",
        "summary": "Test final execution reporting",
        "files": [
            {
                "path": "main.py",
                "content": "print('hello')\n",
            }
        ],
    }

    class MockLLM:
        async def generate(self, **kwargs):
            return json.dumps(project)

    agent.llm = MockLLM()
    agent.set_status = lambda status, data=None: statuses.append(
        (status, data)
    )
    agent._build_prompt = lambda task: "mock prompt"
    agent._parse_project = lambda response: json.loads(response)
    agent._remove_stdlib_requirements = lambda project: False
    agent._validate_project = lambda project: None
    agent._validate_flask_consistency = lambda project: None
    agent._validate_flask_routes = lambda project: None
    agent.write_project_to_workspace = lambda project: "RepairResultTest"

    results = iter(execution_results)
    agent.run_project = lambda path: next(results)

    async def fake_fix_project(path, execution_result):
        assert path == "RepairResultTest"
        assert execution_result["return_code"] != 0
        return {
            "file": "main.py",
            "content": "print('repaired')\n",
        }

    agent.fix_project = fake_fix_project
    agent.inspect_project = lambda path: {
        "RepairResultTest/main.py": "print('hello')\n",
    }
    agent.edit_project_file = lambda *args: edits.append(args)

    return agent, statuses, edits


def test_run_reports_success_when_repair_and_rerun_pass():
    async def run_test():
        agent, statuses, edits = make_agent([
            {
                "return_code": 1,
                "stdout": "",
                "stderr": "Automated project tests failed.",
            },
            {
                "return_code": 0,
                "stdout": "All tests passed",
                "stderr": "",
                "test_result": {"status": "passed", "return_code": 0},
            },
        ])

        response = await agent.run("Build a simple Python application")
        project = json.loads(response)

        assert len(edits) == 1
        assert project["status"] == "success"
        assert project["execution"]["return_code"] == 0
        assert project["execution"]["stdout"] == "All tests passed"
        assert statuses[-1][0] == "idle"
        assert statuses[-1][1]["execution"]["return_code"] == 0

    asyncio.run(run_test())


def test_run_reports_failure_when_repair_and_rerun_still_fail():
    async def run_test():
        agent, statuses, edits = make_agent([
            {
                "return_code": 1,
                "stdout": "",
                "stderr": "Initial test failure",
            },
            {
                "return_code": 1,
                "stdout": "",
                "stderr": "Tests still failing after repair",
                "test_result": {"status": "failed", "return_code": 1},
            },
        ])

        response = await agent.run("Build a simple Python application")
        project = json.loads(response)

        assert len(edits) == 1
        assert project["status"] == "failed"
        assert project["execution"]["return_code"] == 1
        assert "Tests still failing after repair" in project["execution"]["stderr"]
        assert statuses[-1][0] == "failed"
        assert statuses[-1][1]["execution"]["return_code"] == 1

    asyncio.run(run_test())
