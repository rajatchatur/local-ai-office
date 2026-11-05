import sys

import pytest

from backend.core.workspace import Workspace

def test_run_argv_executes_without_shell(tmp_path):
    workspace = Workspace(str(tmp_path))

    result = workspace.run_argv(
        [sys.executable, "-c", "print('safe argv')"],
        timeout=5,
    )

    assert result["return_code"] == 0
    assert result["stdout"].strip() == "safe argv"
    assert result["stderr"] == ""


def test_run_argv_returns_error_when_command_times_out(tmp_path):
    workspace = Workspace(str(tmp_path))

    result = workspace.run_argv(
        [sys.executable, "-c", "import time; time.sleep(2)"],
        timeout=1,
    )

    assert result["return_code"] == 124
    assert "timed out after 1 seconds" in result["stderr"]


def test_run_argv_rejects_cwd_outside_workspace(tmp_path):
    workspace = Workspace(str(tmp_path))

    with pytest.raises(ValueError, match="escapes workspace"):
        workspace.run_argv(
            [sys.executable, "-c", "pass"],
            cwd="../outside",
        )


def test_create_and_edit_file_leave_no_temp_files(tmp_path):
    workspace = Workspace(str(tmp_path))

    workspace.create_file("Demo/main.py", "print('one')\n")
    workspace.edit_file("Demo/main.py", "print('two')\n")

    assert workspace.read_file("Demo/main.py") == "print('two')\n"
    assert list(workspace.root.rglob("*.tmp")) == []

def test_run_command_returns_error_when_command_times_out(tmp_path):
    workspace = Workspace(str(tmp_path))

    result = workspace.run_command(
        f'"{sys.executable}" -c "import time; time.sleep(2)"',
        timeout=1,
    )

    assert result["return_code"] == 124
    assert "timed out after 1 seconds" in result["stderr"]
    assert "stdout" in result
