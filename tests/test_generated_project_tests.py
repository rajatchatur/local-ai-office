import sys

from backend.agents.coder import CoderAgent


class FakeWorkspace:
    def __init__(self, result=None):
        self.result = result or {
            "return_code": 0,
            "stdout": "3 passed",
            "stderr": "",
        }
        self.calls = []

    def run_command(self, command, timeout=60, cwd=None, env=None):
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
    assert agent.workspace.calls[0]["command"] == [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/test_app.py",
    ]
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


def test_javascript_package_test_script_is_discovered():
    agent = make_agent({
        "package.json": (
            '{"name":"demo","scripts":{"test":"node test.js"}}'
        ),
        "index.js": 'console.log("hello");\n',
        "test.js": 'console.log("tests passed");\n',
    })

    result = agent.run_project("Demo")

    assert result["test_result"]["status"] == "passed"
    assert result["test_result"]["return_code"] == 0
    assert agent.workspace.calls[0]["command"] == ["npm", "test"]
    assert agent.workspace.calls[0]["cwd"] == "Demo"
    assert agent.workspace.calls[0]["timeout"] == 120


def test_javascript_package_without_test_script_reports_no_tests():
    agent = make_agent({
        "package.json": '{"name":"demo","scripts":{"start":"node index.js"}}',
        "index.js": 'console.log("hello");\n',
    })

    result = agent.run_project("Demo")

    assert result["test_result"]["status"] == "no_tests"
    assert result["test_result"]["return_code"] == 0
    assert agent.workspace.calls == []


def test_javascript_test_failure_fails_overall_execution():
    agent = make_agent(
        {
            "package.json": (
                '{"name":"demo","scripts":{"test":"node test.js"}}'
            ),
            "index.js": 'console.log("hello");\n',
            "test.js": 'throw new Error("test failed");\n',
        },
        {
            "return_code": 1,
            "stdout": "",
            "stderr": "Error: test failed",
        },
    )

    result = agent.run_project("Demo")

    assert result["return_code"] == 1
    assert result["application_result"]["return_code"] == 0
    assert result["test_result"]["status"] == "failed"
    assert "Automated project tests failed." in result["stderr"]


def test_invalid_package_json_fails_with_clear_result():
    agent = make_agent({
        "package.json": '{"scripts":',
        "index.js": 'console.log("hello");\n',
    })

    result = agent.run_project("Demo")

    assert result["return_code"] == 1
    assert result["test_result"]["status"] == "failed"
    assert "Invalid package.json" in result["test_result"]["stderr"]


def test_invalid_package_scripts_type_fails_clearly():
    agent = make_agent({
        "package.json": '{"scripts":[]}',
        "index.js": 'console.log("hello");\n',
    })

    result = agent.run_project("Demo")

    assert result["return_code"] == 1
    assert result["test_result"]["status"] == "failed"
    assert "scripts must be an object" in result["test_result"]["stderr"]


def test_python_tests_take_precedence_over_npm_script():
    agent = make_agent({
        "package.json": '{"scripts":{"test":"npm run custom-test"}}',
        "main.py": 'print("hello")\n',
        "tests/test_app.py": "def test_example():\n    assert True\n",
    })

    result = agent.run_project("Demo")

    assert result["test_result"]["status"] == "passed"
    assert agent.workspace.calls[0]["command"] == [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/test_app.py",
    ]
