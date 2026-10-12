from pathlib import Path
from typing import Dict, List
import uuid


class ArtifactManager:

    def __init__(
        self,
        base_directory: str = "data/generated",
    ):
        self.base_directory = Path(base_directory)

        self.base_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    def create_project(
        self,
        project_name: str,
        files: List[Dict],
        request_id: str | None = None,
    ):
        request_id = request_id or str(uuid.uuid4())

        safe_project_name = (
            project_name
            .strip()
            .replace(" ", "_")
            .replace("/", "_")
            .replace("\\", "_")
        )

        if not safe_project_name:
            raise ValueError(
                "Project name is required."
            )

        project_directory = (
            self.base_directory
            / request_id
            / safe_project_name
        )

        project_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        created_files = []

        for file in files:

            relative_path = Path(
                str(file.get("path", "")).strip()
            )

            if (
                not relative_path.as_posix()
                or relative_path == Path(".")
                or ".." in relative_path.parts
                or relative_path.is_absolute()
            ):
                raise ValueError(
                    f"Invalid artifact path: {relative_path}"
                )

            content = file.get(
                "content",
                "",
            )

            if not isinstance(content, str):
                content = str(content)

            file_path = (
                project_directory
                / relative_path
            )

            file_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            file_path.write_text(
                content,
                encoding="utf-8",
            )

            created_files.append(
                {
                    "path":
                        relative_path.as_posix(),
                    "size":
                        file_path.stat().st_size,
                }
            )

        return {
            "request_id": request_id,
            "project_name": safe_project_name,
            "project_directory":
                str(project_directory),
            "files": created_files,
        }

    def get_project(
        self,
        request_id: str,
        project_name: str,
    ):

        root = self._safe_project_root(
            request_id,
            project_name,
        )

        if not root.exists():
            raise FileNotFoundError(
                f"Project '{project_name}' not found."
            )

        files = []

        for path in sorted(
            root.rglob("*")
        ):

            if path.is_file():

                files.append(
                    {
                        "path":
                            path.relative_to(
                                root
                            ).as_posix(),
                        "size":
                            path.stat().st_size,
                    }
                )

        return {
            "request_id": request_id,
            "project_name": root.name,
            "files": files,
        }

    def read_file(
        self,
        request_id: str,
        project_name: str,
        file_path: str,
    ):

        root = self._safe_project_root(
            request_id,
            project_name,
        )

        requested = (
            root / file_path
        ).resolve()

        if (
            root.resolve() != requested
            and root.resolve()
            not in requested.parents
        ):
            raise ValueError(
                "Invalid file path."
            )

        if not requested.is_file():
            raise FileNotFoundError(
                file_path
            )

        return requested.read_text(
            encoding="utf-8"
        )

    def _safe_project_root(
        self,
        request_id: str,
        project_name: str,
    ):

        root = (
            self.base_directory
            / request_id
            / project_name
        ).resolve()

        base = (
            self.base_directory
            .resolve()
        )

        if (
            root != base
            and base not in root.parents
        ):
            raise ValueError(
                "Invalid project path."
            )

        return root