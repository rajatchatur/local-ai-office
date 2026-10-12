import sys
import subprocess
from unittest.mock import patch

from backend.agents.coder import CoderAgent

def test_flask_startup_timeout_returns_structured_error(tmp_path):
    agent = object.__new__(CoderAgent)

    class FakeWorkspace:
        def _safe_path(self, project_name):
            return str(tmp_path)
        def run_command(self, command, timeout=60, cwd=None):
            return {
                "return_code": 0,
                "stdout": "",
                "stderr": "",
            }

    agent.workspace = FakeWorkspace()
    agent.inspect_project = lambda project_name: {
        f"{project_name}/main.py": (
            "from flask import Flask\n"
            "app = Flask(__name__)\n"
        )
    }

    timeout_error = subprocess.TimeoutExpired(
        cmd="flask-startup-check",
        timeout=15,
        output=b"startup output",
        stderr=b"startup diagnostic",
    )

    with patch(
            "subprocess.run",
            side_effect=timeout_error,
        ):
        result = agent.run_project("TimeoutTest")

    assert result["return_code"] == 124
    assert result["stdout"] == "startup output"
    assert "timed out after 15 seconds" in result["stderr"]
    assert "startup diagnostic" in result["stderr"]
