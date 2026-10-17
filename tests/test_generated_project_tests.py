from backend.agents.coder import CoderAgent


class FakeWorkspace:
    def __init__(self, result=None):
        self.result = result or {
            "return_code": 0,
            "stdout": "3 passed",
            "stderr": "",
        }
        self.calls = []

    def run_command(self, command, timeout=60, cwd=None):
        self.calls.append({
            "command": command,
            "timeout": timeout,
            "cwd": cwd,
        })
        return self.result


def make_agent(files, command_result=None):
    agent = object.__new__(CoderAgent)
    agent.workspace = FakeWorkspace(command_result)
    agent.inspect_project = lambda name: {
        f"{name}/{path}": content for path, content in files.items()
    }
    agent._run_project_application = lambda name: {
        "return_code": 0,
        "stdout": "Application ran",
        "stderr": "",
    }
    return agent


def test_project_without_tests_is_reported_as_no_tests():
    agent = make_agent({"main.py": "print('hello')\n"})

    result = agent.run_project("Demo")

    assert result["return_code"] == 0
    assert result["test_result"]["status"] == "no_tests"
    assert agent.workspace.calls == []


def test_project_tests_pass():
    agent = make_agent({
        "main.py": "print('hello')\n",
        "tests/test_app.py": "def test_example():\n    assert 1 + 1 == 2\n",
    })

    result = agent.run_project("Demo")

    assert result["return_code"] == 0
    assert result["test_result"]["status"] == "passed"
    assert result["test_result"]["stdout"] == "3 passed"
    assert agent.workspace.calls[0]["command"] == "python -m pytest -q tests/test_app.py"
    assert agent.workspace.calls[0]["cwd"] == "Demo"
    assert agent.workspace.calls[0]["timeout"] == 120


def test_project_test_failure_fails_overall_execution():
    agent = make_agent(
        {
            "main.py": "print('hello')\n",
            "tests/test_app.py": "def test_example():\n    assert False\n",
        },
        {
            "return_code": 1,
            "stdout": "1 failed",
            "stderr": "AssertionError",
        },
    )

    result = agent.run_project("Demo")

    assert result["return_code"] == 1
    assert result["application_result"]["return_code"] == 0
    assert result["test_result"]["status"] == "failed"
    assert result["test_result"]["stdout"] == "1 failed"
    assert "AssertionError" in result["test_result"]["stderr"]
    assert "Automated project tests failed." in result["stderr"]


def test_project_test_runner_passes_only_discovered_test_files():
    agent = make_agent({
        "main.py": "print('hello')\n",
        "tests/test_app.py": "def test_app():\n    assert True\n",
        "tests/test_other.py": "def test_other():\n    assert True\n",
        "helpers/test_helper.py": "def test_helper():\n    assert True\n",
        "venv/lib/python3.11/site-packages/test_dependency.py": (
            "def test_dependency():\n    assert True\n"
        ),
    })

    result = agent.run_project("Demo")

    command = agent.workspace.calls[0]["command"]
    assert "tests/test_app.py" in command
    assert "tests/test_other.py" in command
    assert "helpers/test_helper.py" in command
    assert "test_dependency.py" not in command
    assert result["test_result"]["test_files"] == [
        "helpers/test_helper.py",
        "tests/test_app.py",
        "tests/test_other.py",
    ]
