import os
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path


class Workspace:
    """
    Safe filesystem and command execution interface for the CoderAgent.

    All file operations are restricted to the configured workspace root.
    """

    def __init__(self, root: str):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()

        if path != self.root and self.root not in path.parents:
            raise ValueError(
                f"Path escapes workspace: {relative_path}"
            )

        return path

    def list_files(self) -> list[str]:
        return [
            str(path.relative_to(self.root))
            for path in self.root.rglob("*")
            if path.is_file()
        ]

    def read_file(self, relative_path: str) -> str:
        path = self._safe_path(relative_path)

        if not path.is_file():
            raise FileNotFoundError(
                f"File not found: {relative_path}"
            )

        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(
                f"Cannot read binary or non-UTF-8 file as text: "
                f"{relative_path}"
            ) from exc

    def _atomic_write(
        self,
        path: Path,
        content: str,
    ) -> None:
        fd, temp_name = tempfile.mkstemp(
            dir=str(path.parent),
            prefix=f".{path.name}.",
            suffix=".tmp",
        )

        try:
            with os.fdopen(
                fd,
                "w",
                encoding="utf-8",
                newline="",
            ) as handle:
                handle.write(content)

            if path.exists():
                shutil.copymode(path, temp_name)

            os.replace(temp_name, path)

        except BaseException:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise

    def create_file(
        self,
        relative_path: str,
        content: str,
    ) -> None:
        path = self._safe_path(relative_path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._atomic_write(path, content)

    def edit_file(
        self,
        relative_path: str,
        content: str,
    ) -> None:
        path = self._safe_path(relative_path)

        if not path.is_file():
            raise FileNotFoundError(
                f"File not found: {relative_path}"
            )

        self._atomic_write(path, content)

    def delete_file(
        self,
        relative_path: str,
    ) -> None:
        path = self._safe_path(relative_path)

        if not path.is_file():
            raise FileNotFoundError(
                f"File not found: {relative_path}"
            )

        path.unlink()


    def run_argv(
        self,
        argv: list[str],
        timeout: int = 60,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> dict:
        return self.run_command(
            argv,
            timeout=timeout,
            cwd=cwd,
            env=env,
        )

    def run_command(
        self,
        command: str | list[str],
        timeout: int = 60,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> dict:
        shell = isinstance(command, str)
        argv = command if shell else [str(item) for item in command]

        run_env = os.environ.copy()
        if env:
            run_env.update(env)

        popen_kwargs = {}
        if os.name != "nt":
            popen_kwargs["start_new_session"] = True
        else:
            popen_kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP
            )

        process = subprocess.Popen(
            argv,
            shell=shell,
            cwd=self._safe_path(cwd) if cwd else self.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=run_env,
            **popen_kwargs,
        )

        try:
            stdout, stderr = process.communicate(timeout=timeout)

            return {
                "return_code": process.returncode,
                "stdout": stdout,
                "stderr": stderr,
            }

        except subprocess.TimeoutExpired:
            if os.name == "nt":
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)

            stdout, stderr = process.communicate()

            return {
                "return_code": 124,
                "stdout": stdout,
                "stderr": (
                    f"Command timed out after {timeout} seconds."
                    + (f"\n{stderr}" if stderr else "")
                ),
            }
