import sys

from backend.core.workspace import Workspace

def test_run_command_returns_error_when_command_times_out(tmp_path):
    workspace = Workspace(str(tmp_path))

    result = workspace.run_command(
        f'"{sys.executable}" -c "import time; time.sleep(2)"',
        timeout=1,
    )

    assert result["return_code"] == 124
    assert "timed out after 1 seconds" in result["stderr"]
    assert "stdout" in result
