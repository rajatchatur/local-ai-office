import shutil

import pytest

from backend.agents.coder import CoderAgent
from backend.core.workspace import Workspace


def make_agent(tmp_path, project_name, files):
    project_dir = tmp_path / project_name
    project_dir.mkdir(parents=True)

    for relative_path, content in files.items():
        path = project_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    agent = object.__new__(CoderAgent)
    agent.workspace = Workspace(str(tmp_path))
    agent.inspect_project = lambda name: {
        f"{name}/{relative_path}": content
        for relative_path, content in files.items()
    }
    return agent


@pytest.fixture(autouse=True)
def require_node():
    if not shutil.which("node"):
        pytest.skip("Node.js is required")


def test_javascript_hello_world_runs(tmp_path):
    agent = make_agent(
        tmp_path,
        "JavaScriptHello",
        {
            "index.js": (
                'console.log("Hello from Local AI Office");\n'
            )
        },
    )

    result = agent.run_project("JavaScriptHello")

    assert result["return_code"] == 0, result["stderr"]
    assert result["stdout"].strip() == "Hello from Local AI Office"


def test_javascript_syntax_error_returns_failure(tmp_path):
    agent = make_agent(
        tmp_path,
        "JavaScriptSyntaxError",
        {"index.js": 'console.log("missing quote);\n'},
    )

    result = agent.run_project("JavaScriptSyntaxError")

    assert result["return_code"] != 0
    assert result["stderr"].strip()


def test_javascript_runtime_error_returns_failure(tmp_path):
    agent = make_agent(
        tmp_path,
        "JavaScriptRuntimeError",
        {"index.js": 'throw new Error("intentional test failure");\n'},
    )

    result = agent.run_project("JavaScriptRuntimeError")

    assert result["return_code"] != 0
    assert "intentional test failure" in result["stderr"]


def test_javascript_entry_point_is_required_when_ambiguous(tmp_path):
    agent = make_agent(
        tmp_path,
        "JavaScriptAmbiguous",
        {
            "first.js": 'console.log("first");\n',
            "second.js": 'console.log("second");\n',
        },
    )

    result = agent.run_project("JavaScriptAmbiguous")

    assert result["return_code"] != 0
    assert "entry point" in result["stderr"].lower()


def test_javascript_timeout_returns_structured_failure(tmp_path):
    agent = make_agent(
        tmp_path,
        "JavaScriptTimeout",
        {"index.js": "setTimeout(() => {}, 10000);\n"},
    )

    original_run_command = agent.workspace.run_command

    def short_timeout(command, timeout=60, cwd=None, env=None):
        argv = command if isinstance(command, list) else command.split()

        if argv[:2] == ["node", "--check"]:
            return original_run_command(
                command, timeout=timeout, cwd=cwd, env=env
            )

        return original_run_command(
            command, timeout=2, cwd=cwd, env=env
        )

    agent.workspace.run_command = short_timeout

    result = agent.run_project("JavaScriptTimeout")

    assert result["return_code"] == 124
    assert "timed out" in result["stderr"].lower()

    def simulate_timeout(command, timeout=60, cwd=None, env=None):
        argv = command if isinstance(command, list) else command.split()

        if argv[:2] == ["node", "--check"]:
            return {
                "return_code": 0,
                "stdout": "",
                "stderr": "",
            }
        return {
            "return_code": 124,
            "stdout": "",
            "stderr": "Command timed out after 2 seconds.",
        }

    agent.workspace.run_command = simulate_timeout

    result = agent.run_project("JavaScriptTimeout")

    assert result["return_code"] == 124
    assert "timed out" in result["stderr"].lower()


def test_javascript_literal_newline_escapes_are_repaired(tmp_path):
    agent = make_agent(
        tmp_path,
        "JavaScriptEscapedNewlines",
        {
            "index.js": (
                r'console.log("Hello from Local AI Office");\n'
                r'console.log("JavaScript execution is working");\n'
                r'console.log("Program Output panel test passed");'
            )
        },
    )

    result = agent.run_project("JavaScriptEscapedNewlines")

    assert result["return_code"] == 0, result["stderr"]
    assert result["stdout"].splitlines() == [
        "Hello from Local AI Office",
        "JavaScript execution is working",
        "Program Output panel test passed",
    ]
