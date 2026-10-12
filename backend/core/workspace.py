from pathlib import Path
import subprocess


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

        path.write_text(
            content,
            encoding="utf-8",
        )

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

        path.write_text(
            content,
            encoding="utf-8",
        )

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


    def run_command(
        self,
        command: str,
        timeout: int = 60,
        cwd: str | None = None,
    ) -> dict:
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self._safe_path(cwd) if cwd else self.root,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            return {
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""

            # subprocess may return captured output as bytes on timeout.
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")

            return {
                "return_code": 124,
                "stdout": stdout,
                "stderr": (
                    f"Command timed out after {timeout} seconds."
                    + (f"\n{stderr}" if stderr else "")
                ),
            }
