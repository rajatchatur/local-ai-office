import asyncio
import ast
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from backend.agents.base_agent import BaseAgent
from backend.llm.llama_cpp_client import LlamaCppClient
from backend.core.workspace import Workspace

PYTHON_PACKAGE_MAP = {
    "kafka": "kafka-python",
    "requests": "requests",
    "httpx": "httpx",
    "fastapi": "fastapi",
    "flask": "flask",
    "flask_restful": "Flask-RESTful",
    "flask_sqlalchemy": "Flask-SQLAlchemy",
    "flask_cors": "Flask-Cors",
    "pandas": "pandas",
    "numpy": "numpy",
    "boto3": "boto3",
    "snowflake": "snowflake-connector-python",
    "flask_caching": "flask-caching",
    "flask_wtf": "flask-wtf",
    "flask_login": "flask-login",
    "flask_bcrypt": "Flask-Bcrypt",
    "flask_migrate": "Flask-Migrate",
    "flask_socketio": "Flask-SocketIO",
    "flask_jwt_extended": "Flask-JWT-Extended",
    "flask_mail": "Flask-Mail",
    "flask_limiter": "Flask-Limiter",
    "flask_marshmallow": "flask-marshmallow",
    "marshmallow": "marshmallow",
    "uvicorn": "uvicorn",
    "pydantic": "pydantic",
    "sqlalchemy": "sqlalchemy",
    "redis": "redis",
    "jwt": "pyjwt",
    "passlib": "passlib",
    "bcrypt": "bcrypt",
    "bs4": "beautifulsoup4",
    "matplotlib": "matplotlib",
    "sklearn": "scikit-learn",
    "tabulate": "tabulate",
    "psycopg2": "psycopg2-binary",
    "pymysql": "pymysql",
    "dotenv": "python-dotenv",
    "dateutil": "python-dateutil",
    "yaml": "pyyaml",
    "PIL": "pillow",
    "geopy": "geopy",
    "rich": "rich",
    "click": "click",
    "jinja2": "jinja2",
    "pytest": "pytest",
}
PYTHON_STDLIB_MODULES = {
    "abc",
    "argparse",
    "ast",
    "asyncio",
    "base64",
    "collections",
    "csv",
    "datetime",
    "functools",
    "hashlib",
    "http",
    "itertools",
    "json",
    "logging",
    "math",
    "os",
    "pathlib",
    "re",
    "secrets",
    "shutil",
    "sqlite3",
    "statistics",
    "string",
    "subprocess",
    "sys",
    "tempfile",
    "textwrap",
    "threading",
    "time",
    "typing",
    "unittest",
    "urllib",
    "uuid",
    "warnings",
    "xml",
}


class CoderAgent(BaseAgent):
    """
    Coder agent responsible for generating complete software projects.

    The agent returns a structured JSON project definition:

    {
        "project_name": "...",
        "summary": "...",
        "files": [
            {
                "path": "main.py",
                "content": "..."
            }
        ]
    }

    The JSON response is generated using Ollama's JSON mode so that
    Python source code containing quotes/newlines does not break parsing.
    """

    def __init__(self, event_bus=None, message_bus=None):
        super().__init__(
            name="coder",
            role="Software Developer",
            event_bus=event_bus,
        )

        self.message_bus = message_bus

        self._project_locks: dict[str, asyncio.Lock] = {}

        self.llm = LlamaCppClient(
            model="qwen3-1.7b"
        )
        workspace_path = os.getenv("LOCAL_AI_OFFICE_WORKSPACE")
        if not workspace_path:
            workspace_path = str(
                Path(__file__).resolve().parents[2] / "workspace"
            )
        self.workspace = Workspace(workspace_path)

    def _project_lock(self, project_name: str) -> asyncio.Lock:
        locks = getattr(self, "_project_locks", None)
        if locks is None:
            locks = {}
            self._project_locks = locks

        lock = locks.get(project_name)
        if lock is None:
            lock = asyncio.Lock()
            locks[project_name] = lock

        return lock

    @staticmethod
    def _repair_javascript_newline_separators(content: str) -> str:
        """Repair literal \n separators between recognizable JS statements."""
        return re.sub(
            r";\\n(?=\s*(?:console\.|const\s|let\s|var\s|function\s|if\s|return\s|//|$))",
            ";\n",
            content,
        )

    def _repair_flask_db_context(self, content: str) -> str:
        """
        Flask-SQLAlchemy needs an app context for db.create_all(). Wrap any
        bare db.create_all() call in `with app.app_context():` when the file
        does not already do so.
        """
        if "db.create_all()" not in content or "app_context()" in content:
            return content

        import re

        def wrap(match):
            indent = match.group(1)
            return (
                f"{indent}with app.app_context():\n"
                f"{indent}    db.create_all()"
            )

        return re.sub(
            r"^([ \t]*)db\.create_all\(\)[ \t]*$",
            wrap,
            content,
            flags=re.M,
        )

    def write_project_to_workspace(
        self, project: dict, preserve_existing: bool = False
    ) -> str:
        """
        Write a generated Project to the local workspace.
        """

        project_dir = project["project_name"].strip()

        for file in project["files"]:
            relative_path = file["path"]
            content = file["content"]

            if relative_path.lower().endswith(".js"):
                content = self._repair_javascript_newline_separators(
                    content
                )

            if relative_path.lower().endswith(".py"):
                content = self._repair_flask_db_context(content)

            file_path = f"{project_dir}/{relative_path}"

            if preserve_existing and file_path in set(self.workspace.list_files()):
                print(f"CODER: Preserving existing file: {file_path}")
                continue

            self.workspace.create_file(
                file_path,
                content,
            )

        return project_dir


    def _unique_project_name(self, project_name: str) -> str:
        """
        Return project_name, or project_name_2, _3, ... if that folder is
        already in the workspace. Normal generation never overwrites a
        project, so a taken name is renamed instead of failing.
        """
        workspace = getattr(self, "workspace", None)
        if workspace is None:
            return project_name

        candidate = project_name
        suffix = 2

        while workspace._safe_path(candidate).exists():
            candidate = f"{project_name}_{suffix}"
            suffix += 1

        return candidate

    def _ensure_project_directory_available(self, project_name: str) -> None:
        """Prevent normal generation from overwriting an existing project."""
        workspace = getattr(self, "workspace", None)

        # Some unit tests replace the writer with a mock and intentionally
        # construct a lightweight agent without initializing its workspace.
        writer = self.write_project_to_workspace
        if workspace is None and getattr(writer, "__self__", None) is not self:
            return
        if workspace is None:
            raise RuntimeError("CoderAgent workspace is not initialized")

        project_path = workspace._safe_path(project_name)
        if project_path.exists():
            raise FileExistsError(
                f"Project directory already exists: {project_name}. "
                "Existing projects are never overwritten by normal generation. "
                "Ask to update the existing project and name the files to change."
            )


    def _run_java_project(
        self,
        project_name: str,
        project_files: dict,
    ) -> dict:
        """Compile and run a Java project in its workspace directory."""
        import re

        prefix = f"{project_name}/"
        java_files = [
            (path[len(prefix):], content)
            for path, content in project_files.items()
            if path.startswith(prefix) and path.endswith(".java")
        ]

        if not java_files:
            return {
                "return_code": 1,
                "stdout": "",
                "stderr": "Java project contains no .java source files.",
            }

        main_class = None

        for relative_path, content in java_files:
            if not re.search(
                r"\bstatic\s+void\s+main\s*\(\s*String\s*\[\s*\]",
                content,
            ):
                continue

            class_match = re.search(
                r"\b(?:public\s+)?(?:final\s+)?class\s+"
                r"([A-Za-z_$][\w$]*)",
                content,
            )
            if not class_match:
                continue

            package_match = re.search(
                r"^\s*package\s+([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*;",
                content,
                re.MULTILINE,
            )
            class_name = class_match.group(1)

            main_class = (
                f"{package_match.group(1)}.{class_name}"
                if package_match
                else class_name
            )
            break

        if main_class is None:
            return {
                "return_code": 1,
                "stdout": "",
                "stderr": (
                    "Could not find a Java class with "
                    "public static void main(String[] args)."
                ),
            }

        print("CODER: Compiling Java project...")
        compile_result = self.workspace.run_command(
            ["javac", "-d", ".", *[path for path, _ in java_files]],
            cwd=project_name,
            timeout=60,
        )

        if compile_result["return_code"] != 0:
            return compile_result

        print(f"CODER: Running Java class: {main_class}")
        return self.workspace.run_command(
            ["java", "-cp", ".", main_class],
            cwd=project_name,
            timeout=60,
        )

    def _run_javascript_project(
        self,
        project_name: str,
        project_files: dict,
    ) -> dict:
        """Run a JavaScript project with Node.js."""
        prefix = f"{project_name}/"
        js_files = [
            path[len(prefix):]
            for path in project_files
            if path.startswith(prefix)
            and path.endswith(".js")
            and "/node_modules/" not in path
        ]

        if not js_files:
            return {
                "return_code": 1,
                "stdout": "",
                "stderr": "JavaScript project contains no .js source files.",
            }

        preferred = ("index.js", "main.js", "app.js")
        entry_point = next(
            (name for name in preferred if name in js_files),
            None,
        )

        if entry_point is None:
            top_level = [name for name in js_files if "/" not in name]
            if len(top_level) == 1:
                entry_point = top_level[0]
            elif len(js_files) == 1:
                entry_point = js_files[0]

        if entry_point is None:
            return {
                "return_code": 1,
                "stdout": "",
                "stderr": (
                    "Could not determine the JavaScript entry point. "
                    "Include index.js or main.js, or provide exactly one "
                    "JavaScript source file."
                ),
            }

        source_path = f"{project_name}/{entry_point}"
        source_content = project_files.get(source_path)

        if isinstance(source_content, str):
            repaired_content = self._repair_javascript_newline_separators(
                source_content
            )
            if repaired_content != source_content:
                self.workspace.edit_file(source_path, repaired_content)
                print(
                    "CODER: Repaired escaped newline separators in "
                    f"{entry_point}"
                )

        print(f"CODER: Running JavaScript entry point: {entry_point}")
        syntax_result = self.workspace.run_command(
            ["node", "--check", entry_point],
            cwd=project_name,
            timeout=60,
        )

        if syntax_result["return_code"] != 0:
            return syntax_result

        print(f"CODER: Executing JavaScript entry point: {entry_point}")
        return self.workspace.run_command(
            ["node", entry_point],
            cwd=project_name,
            timeout=60,
        )

    def run_project(self, project_name: str) -> dict:
        """Run the application and any discovered Python test suite."""
        application_result = self._run_project_application(project_name)
        result = dict(application_result)
        result["application_result"] = dict(application_result)

        test_result = self._run_project_tests(project_name)
        result["test_result"] = test_result

        if test_result["return_code"] != 0:
            if result["return_code"] == 0:
                result["return_code"] = test_result["return_code"]

            test_stderr = test_result.get("stderr", "")
            message = "Automated project tests failed."
            if test_stderr:
                message += "\n" + test_stderr
            result["stderr"] = (
                result.get("stderr", "").rstrip()
                + ("\n" if result.get("stderr", "").strip() else "")
                + message
            )

        return result

    def _run_project_tests(self, project_name: str) -> dict:
        """Run discovered Python tests or an explicit npm test script."""
        import json
        from pathlib import PurePosixPath

        project_files = self.inspect_project(project_name)
        prefix = f"{project_name}/"
        excluded_parts = {
            "__pycache__", ".venv", "venv", "site-packages", "node_modules"
        }

        test_files = []
        for path in project_files:
            if not path.startswith(prefix) or not path.endswith(".py"):
                continue

            relative_path = path[len(prefix):]
            parts = PurePosixPath(relative_path).parts
            if any(part in excluded_parts for part in parts):
                continue

            filename = PurePosixPath(relative_path).name
            if filename.startswith("test_") or filename.endswith("_test.py"):
                test_files.append(relative_path)

        if test_files:
            test_files = sorted(set(test_files))
            test_command = [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                *test_files,
            ]
            print(f"CODER: Running {len(test_files)} project test file(s)...")
            execution = self.workspace.run_command(
                test_command,
                cwd=project_name,
                timeout=120,
            )
            return {
                "status": "passed" if execution["return_code"] == 0 else "failed",
                "return_code": execution["return_code"],
                "stdout": execution["stdout"],
                "stderr": execution["stderr"],
                "test_files": test_files,
            }

        manifest_path = f"{project_name}/package.json"
        if manifest_path in project_files:
            try:
                manifest = json.loads(project_files[manifest_path])
            except (json.JSONDecodeError, TypeError) as exc:
                return {
                    "status": "failed",
                    "return_code": 1,
                    "stdout": "",
                    "stderr": f"Invalid package.json: {exc}",
                    "test_files": [],
                }

            if not isinstance(manifest, dict):
                return {
                    "status": "failed",
                    "return_code": 1,
                    "stdout": "",
                    "stderr": "Invalid package.json: expected a JSON object.",
                    "test_files": [],
                }

            scripts = manifest.get("scripts", {})
            if not isinstance(scripts, dict):
                return {
                    "status": "failed",
                    "return_code": 1,
                    "stdout": "",
                    "stderr": "Invalid package.json: scripts must be an object.",
                    "test_files": [],
                }

            test_script = scripts.get("test")
            if isinstance(test_script, str) and test_script.strip():
                print("CODER: Running project npm test script...")
                execution = self.workspace.run_command(
                    ["npm", "test"],
                    cwd=project_name,
                    timeout=120,
                )
                return {
                    "status": (
                        "passed" if execution["return_code"] == 0 else "failed"
                    ),
                    "return_code": execution["return_code"],
                    "stdout": execution["stdout"],
                    "stderr": execution["stderr"],
                    "test_files": ["package.json"],
                }

        return {
            "status": "no_tests",
            "return_code": 0,
            "stdout": "",
            "stderr": "",
            "test_files": [],
        }

    def _run_project_application(self, project_name: str) -> dict:
        """
        Install dependencies, validate Python syntax, and check
        whether the generated application can start.
        """
        project_files = self.inspect_project(project_name)
        print("DEBUG project_name:", repr(project_name))
        print("DEBUG project_files:", list(project_files.keys()))

        # Keep Python projects on the existing, tested execution path.
        has_python = any(
            path.startswith(f"{project_name}/") and path.endswith(".py")
            for path in project_files
        )
        has_java = any(
            path.startswith(f"{project_name}/") and path.endswith(".java")
            for path in project_files
        )

        has_javascript = any(
            path.startswith(f"{project_name}/")
            and path.endswith(".js")
            and "/node_modules/" not in path
            for path in project_files
        )

        if has_java and not has_python and not has_javascript:
            return self._run_java_project(project_name, project_files)

        if has_javascript and not has_python and not has_java:
            return self._run_javascript_project(
                project_name, project_files
            )

        # 1. Install dependencies when requirements.txt exists.
        requirements_path = f"{project_name}/requirements.txt"

        if requirements_path in project_files:
            print("\nCODER: Installing project dependencies...")

            install_result = self.workspace.run_command(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    "requirements.txt",
                ],
                cwd=project_name,
                timeout=300,
            )

            if install_result["return_code"] != 0:
                print("CODER: Dependency installation failed.")
                return install_result

            print("CODER: Dependencies installed.")

        # 2. Check Python syntax.
        print("\nCODER: Checking project syntax...")

        syntax_result = self.workspace.run_command(
            [sys.executable, "-m", "compileall", "-q", "."],
            cwd=project_name,
            timeout=60,
        )

        if syntax_result["return_code"] != 0:
            return syntax_result

        # 3. Find the application's Python entry point.
        # Paths returned by inspect_project() include the project directory.
        python_files = [
            path[len(f"{project_name}/"):]
            for path in project_files
            if path.startswith(f"{project_name}/")
            and path.endswith(".py")
            and "/__pycache__/" not in path
            and not path.endswith(".pyc")
        ]

        if "main.py" in python_files:
            entry_point = "main.py"
        else:
            top_level_files = [
                path for path in python_files
                if "/" not in path
            ]

            if len(top_level_files) == 1:
                entry_point = top_level_files[0]
            else:
                return {
                    "return_code": 1,
                    "stdout": "",
                    "stderr": (
                        "Could not determine the application entry point. "
                        "Include main.py or provide exactly one top-level "
                        "Python file."
                    ),
                }


        print(f"CODER: Selected entry point: {entry_point}")

        # 4. Identify Flask applications.
        is_flask_app = any(
            (
                "from flask import" in content
                or "import flask" in content
            )
            and "Flask(" in content
            for path, content in project_files.items()
            if path.endswith(".py")
        )

        if is_flask_app:
            print("\nCODER: Checking Flask application startup...")

            # Load the selected entry point and bind Flask to an
            # available local port. The server is closed after the check.

            startup_script = (
                "import runpy\n"
                "from werkzeug.serving import make_server\n"
                f"namespace = runpy.run_path({entry_point!r})\n"
                "app = namespace.get('app')\n"
                f"assert app is not None, "
                f"{(entry_point + ' must expose a Flask app named app')!r}\n"
                "server = make_server('127.0.0.1', 0, app)\n"
                "print('STARTUP_OK', server.server_port)\n"
                "server.server_close()\n"
            )

            result = self.workspace.run_command(
                [sys.executable, "-c", startup_script],
                cwd=project_name,
                timeout=15,
            )

            if result["return_code"] == 124:
                result["stderr"] = (
                    "Flask startup check timed out after 15 seconds."
                    + (f"\n{result['stderr']}" if result["stderr"] else "")
                )

            if result["return_code"] == 0:
                print("CODER: Flask startup check passed.")
            else:
                print("CODER: Flask startup check failed.")

            return result



        # 5. For non-Flask projects, run the selected entry point.
        print("\nCODER: Running project...")

        return self.workspace.run_command(
            [sys.executable, entry_point],
            cwd=project_name,
            timeout=60,
        )



    def _repair_missing_test_import(
        self,
        project_name: str,
        execution_result: dict,
    ) -> tuple[str, str] | None:
        """Safely add an import for a project symbol missing from a test."""
        from pathlib import PurePosixPath

        if not isinstance(execution_result, dict):
            return None

        output_parts = [
            str(execution_result.get("stderr") or ""),
            str(execution_result.get("stdout") or ""),
        ]
        test_result = execution_result.get("test_result")
        if isinstance(test_result, dict):
            output_parts.extend([
                str(test_result.get("stderr") or ""),
                str(test_result.get("stdout") or ""),
            ])
        output = "\n".join(output_parts)

        # Restrict this fallback to explicit pytest NameError reports.
        failure = None
        suffix = " is not defined"
        marker = ": NameError: name "
        for line in output.splitlines():
            if marker not in line or not line.endswith(suffix):
                continue

            location, reported_name = line.split(marker, 1)
            if ":" not in location or len(reported_name) <= len(suffix) + 2:
                continue

            candidate_path, line_number = location.rsplit(":", 1)
            quote = reported_name[0]
            if quote not in ("'", '"') or not reported_name.endswith(quote + suffix):
                continue

            symbol_candidate = reported_name[1:-(len(suffix) + 1)]
            if (
                not line_number.isdigit()
                or not candidate_path.endswith(".py")
                or not symbol_candidate.isidentifier()
            ):
                continue

            failure = (candidate_path, line_number, symbol_candidate)
            break

        if failure is None:
            return None

        test_path, _, symbol = failure
        test_path = test_path.replace("\\", "/")
        test_path = test_path.removeprefix(f"{project_name}/")
        test_posix = PurePosixPath(test_path)

        # Permit nested test files but reject absolute paths and traversal.
        if (
            test_posix.is_absolute()
            or ".." in test_posix.parts
            or not test_posix.name.endswith(".py")
            or not (
                test_posix.name.startswith("test_")
                or test_posix.name.endswith("_test.py")
            )
        ):
            return None

        files = self.inspect_project(project_name)
        test_key = f"{project_name}/{test_path}"
        test_content = files.get(test_key)
        if not isinstance(test_content, str):
            return None

        try:
            test_tree = ast.parse(test_content)
        except SyntaxError:
            return None

        # Don't interfere if the test already defines or imports the symbol.
        for node in test_tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name == symbol:
                    return None
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if (alias.asname or alias.name.split(".")[0]) == symbol:
                        return None
            elif isinstance(node, ast.ImportFrom):
                if any((alias.asname or alias.name) == symbol for alias in node.names):
                    return None
            elif isinstance(node, ast.Assign):
                if any(
                    isinstance(target, ast.Name) and target.id == symbol
                    for target in node.targets
                ):
                    return None

        # Require exactly one root-level source module defining the symbol.
        candidates = []
        for key, content in files.items():
            if not key.startswith(f"{project_name}/") or not key.endswith(".py"):
                continue
            relative = key[len(project_name) + 1:]
            if relative == test_path or len(PurePosixPath(relative).parts) != 1:
                continue
            if PurePosixPath(relative).name.startswith("test_") or PurePosixPath(relative).name.endswith("_test.py"):
                continue
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue

            if any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and node.name == symbol
                for node in tree.body
            ):
                candidates.append(PurePosixPath(relative).stem)

        if len(candidates) != 1:
            return None

        module = candidates[0]
        import_line = f"from {module} import {symbol}"

        # Avoid duplicate imports, including aliased imports.
        if import_line in test_content.splitlines():
            return None

        lines = test_content.splitlines(keepends=True)
        insertion_index = 0

        # Preserve a module docstring and any future imports.
        if test_tree.body and isinstance(test_tree.body[0], ast.Expr):
            value = test_tree.body[0].value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                insertion_index = getattr(test_tree.body[0], "end_lineno", 1)

        for node in test_tree.body:
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "__future__"
            ):
                insertion_index = max(
                    insertion_index, getattr(node, "end_lineno", node.lineno)
                )

        # Place the new import after the existing leading import block.
        for node in test_tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                insertion_index = max(
                    insertion_index, getattr(node, "end_lineno", node.lineno)
                )
            elif node.lineno > insertion_index + 1:
                break

        lines.insert(insertion_index, import_line + "\n")
        repaired_content = "".join(lines)

        try:
            ast.parse(repaired_content)
        except SyntaxError:
            return None

        print(
            "CODER: Deterministic test-import repair: "
            f"{test_path} imports {symbol} from {module}."
        )
        return test_path, repaired_content


    def inspect_project(self, project_name: str) -> dict:
        """
        Read generated project text files, excluding caches and environments.
        Skip binary and non-UTF-8 files safely.
        """
        from pathlib import PurePosixPath

        ignored_directories = {
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            ".tox",
            ".venv",
            "venv",
            "env",
            "site-packages",
            "node_modules",
        }

        project_prefix = f"{project_name}/"
        result = {}

        for path in self.workspace.list_files():
            if not path.startswith(project_prefix):
                continue

            relative_path = PurePosixPath(path[len(project_prefix):])
            if any(
                part in ignored_directories
                for part in relative_path.parts[:-1]
            ):
                continue

            try:
                result[path] = self.workspace.read_file(path)
            except (UnicodeDecodeError, ValueError):
                print(f"CODER: Skipping binary file: {path}")
            except FileNotFoundError:
                print(f"CODER: File disappeared during inspection: {path}")

        return result


    def edit_project_file(
        self,
        project_name: str,
        file_path: str,
        content: str,
    ) -> None:
        """
        Replace the contents of an existing project file.
        """

        project_file = f"{project_name}/{file_path}"

        self.workspace.edit_file(
            project_file,
            content,
        )
    async def fix_project(
        self,
        project_name: str,
        execution_result: dict,
    ) -> dict:
        """
        Ask the local LLM to diagnose an execution failure
        and return the file that needs to be fixed.
        """

        files = self.inspect_project(project_name)

        prompt = f"""
    You are debugging a Python project.

    Project:
    {project_name}

    Execution result:
    {execution_result}

    Project files:
    {json.dumps(files, indent=2)}

    Diagnose the failure using the execution result and the complete
    project files. Treat test failures as part of the project failure.

    For Python projects:
    - Read the complete traceback and identify the exact failing file and line.
    - If a test uses a function or class without defining or importing it,
      add the correct import from the application module.
    - Check for NameError, ImportError, ModuleNotFoundError, assertion
      failures, and incorrect expected values.
    - Check test modules for missing imports before changing application code.
    - Preserve tests and application behavior that are already correct.
    - Make the smallest change that resolves the actual failure.
    - Ensure the proposed fix addresses the reported error, not just syntax.

    Return ONLY valid JSON:

    {{
    "file": "relative/path.py",
    "content": "complete corrected file content"
    }}

    Rules:
    - Fix only the problem causing the execution failure.
    - Return the complete corrected content of the file.
    - Do not return markdown.
    - Do not explain anything.
    - Do not create unnecessary files.
    """

        result = await self.llm.generate(
            prompt=prompt,
            format="json",
            temperature=0.1,
            max_tokens=1200,
        )

        try:
            fix = json.loads(result)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError(
                f"Invalid repair response JSON: {exc}"
            ) from exc

        if not isinstance(fix, dict):
            raise ValueError("Invalid repair response")

        return fix

    def _validate_symbol_preservation(
        self,
        old_content: str,
        new_content: str,
        task: str,
    ) -> None:
        if re.search(r"\b(remove|delete)\b", task, re.I):
            return

        try:
            old_tree = ast.parse(old_content)
            new_tree = ast.parse(new_content)
        except SyntaxError:
            return

        def symbols(tree):
            return {
                node.name
                for node in tree.body
                if isinstance(
                    node,
                    (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
                )
            }

        removed = symbols(old_tree) - symbols(new_tree)
        if removed:
            raise ValueError(
                "Repair would remove existing symbols: "
                + ", ".join(sorted(removed))
            )

    def _validate_repair(
        self,
        project_name: str,
        fix: dict,
        task: str = "",
    ) -> tuple[str, str]:
        if not isinstance(fix, dict):
            raise ValueError("Invalid repair response")

        file_path = fix.get("file")
        content = fix.get("content")

        if not isinstance(file_path, str) or not file_path.strip():
            raise ValueError("unsafe repair path: empty or invalid path")

        if not isinstance(content, str):
            raise ValueError("Invalid repair content")

        prefix = f"{project_name}/"
        if file_path.startswith(prefix):
            file_path = file_path[len(prefix):]

        normalized_path = file_path.replace("\\", "/")

        if (
            not normalized_path
            or normalized_path.startswith("/")
            or "\\" in file_path
            or ".." in normalized_path.split("/")
        ):
            raise ValueError(f"unsafe repair path: {file_path}")

        project_files = self.inspect_project(project_name)
        allowed_paths = {
            path.removeprefix(prefix).replace("\\", "/")
            for path in project_files
        }

        if normalized_path not in allowed_paths:
            raise ValueError(
                f"unsafe repair path: file is not in the existing project: "
                f"{normalized_path}"
            )

        if normalized_path.endswith(".py"):
            try:
                ast.parse(content)
            except SyntaxError as exc:
                raise ValueError(
                    f"Invalid Python repair for {normalized_path}: {exc}"
                ) from exc

            self._validate_symbol_preservation(
                project_files[prefix + normalized_path],
                content,
                task,
            )

        return normalized_path, content

    async def repair_existing_project(
        self,
        project_name: str,
    ) -> dict:
        """
        Run an existing project, diagnose failures,
        apply an LLM-generated fix, and run it again.
        """

        print(f"\nCODER: Testing existing project '{project_name}'...")

        execution_result = await asyncio.to_thread(self.run_project, project_name)

        if execution_result["return_code"] == 0:
            return {
                "project_name": project_name,
                "status": "success",
                "execution": execution_result,
            }

        print("\nCODER: Existing project failed.")
        print(execution_result)

        repair_attempts = 0
        fix = None

        while (
            execution_result["return_code"] != 0
            and repair_attempts < 2
        ):
            repair_attempts += 1

            fix = await self.fix_project(
                project_name,
                execution_result,
            )

            print("\nCODER: LLM generated fix:")
            print(fix)

            normalized_path, content = self._validate_repair(
                project_name,
                fix,
            )

            self.edit_project_file(
                project_name,
                normalized_path,
                content,
            )

            print("\nCODER: Fix applied.")
            print("CODER: Running project again...")

            execution_result = await asyncio.to_thread(self.run_project, project_name)

        return {
            "project_name": project_name,
            "status": (
                "success"
                if execution_result["return_code"] == 0
                else "failed"
            ),
            "fix": fix,
            "repair_attempts": repair_attempts,
            "execution": execution_result,
        }


    async def fix_generated_file(
    self,
    file_path: str,
    content: str,
    syntax_error: str,
) -> str:
        """
        Ask the local LLM to repair one generated source file
        that contains a Python syntax error.
        """

        prompt = f"""
    You are fixing one generated Python source file.

    FILE:
    {file_path}

    PYTHON SYNTAX ERROR:
    {syntax_error}

    BROKEN FILE:
    {content}

    Fix ONLY the Python syntax error.

    Rules:
    - Return ONLY the complete corrected Python source code.
    - Do not return JSON.
    - Do not use markdown.
    - Do not explain anything.
    - Preserve the existing functionality.
    - Do not remove requested features.
    - Do not add fake APIs.
    - Do not add new dependencies.
    - Return valid Python code.
    """

        result = await self.llm.generate(
            prompt=prompt,
            temperature=0.0,
            max_tokens=1200,
        )

        return result.strip()
    def _find_existing_project_update(self, task: str):
        """Identify an explicitly named existing project update request."""
        task_lower = task.casefold()

        # Keep explicit new-project requests in the normal generation flow,
        # even if they mention an existing project as inspiration.
        slash = chr(92)
        new_project_pattern = (
            slash + r"b(?:create|build|generate|scaffold|start)"
            + slash + r"s+(?:(?:a|an)" + slash + r"s+)?"
            + r"(?:new" + slash + r"s+)?(?:project|application|app)"
            + slash + "b"
        )
        if re.search(new_project_pattern, task_lower):
            return None

        update_intent = re.search(
            r"\b(add|update|edit|modify|change|document|documentation|readme)\b",
            task_lower,
        )
        if not update_intent:
            return None

        project_names = sorted(
            {
                item.split("/", 1)[0]
                for item in self.workspace.list_files()
                if "/" in item
            },
            key=len,
            reverse=True,
        )

        for name in project_names:
            if re.search(
                r"(?<![\w])" + re.escape(name.casefold()) + r"(?![\w])",
                task_lower,
            ):
                docs_only = self._is_docs_only_update(task_lower)
                return name, docs_only

        return None

    @staticmethod
    def _is_docs_only_update(task: str) -> bool:
        """Return true only when the request does not name source files."""
        if not re.search(r"\b(readme|documentation|docs)\b", task, re.I):
            return False
        if re.search(
            r"\b(source code|application code|implement|refactor)\b",
            task,
            re.I,
        ):
            return False
        # A source/configuration filename in the request makes it a
        # scoped file update, even when the request also mentions a README.
        if re.search(
            r"(?<![\w.-])[\w./-]+\.(?:py|pyw|js|jsx|ts|tsx|mjs|cjs|"
            r"java|kt|go|rs|c|h|cpp|hpp|cs|rb|php|swift|scala|sh|bash|"
            r"html|css|json|yaml|yml|toml|ini|cfg|env|sql)(?![\w.-])",
            task,
            re.I,
        ):
            return False
        return True

    @staticmethod
    def _validate_update_relative_path(relative_path: str) -> str:
        """Reject absolute paths, Windows paths, and directory traversal."""
        if (
            not isinstance(relative_path, str)
            or not relative_path
            or relative_path != relative_path.strip()
            or "\x00" in relative_path
            or relative_path.startswith("/")
            or "\\" in relative_path
            or ":" in relative_path
            or any(part in ("", ".", "..") for part in relative_path.split("/"))
        ):
            raise ValueError(f"Unsafe existing-project file path: {relative_path!r}")
        return relative_path

    async def _update_existing_project(self, task: str, project_name: str) -> str:
        """Update only explicitly permitted files in an existing project."""
        async with self._project_lock(project_name):
            return await self._update_existing_project_locked(
                task,
                project_name,
            )

    async def _update_existing_project_locked(
        self,
        task: str,
        project_name: str,
    ) -> str:
        listed_files = set(self.workspace.list_files())
        project_prefix = f"{project_name}/"
        project_files = sorted(
            item[len(project_prefix):]
            for item in listed_files
            if item.startswith(project_prefix) and item != project_prefix
        )

        if not project_files:
            raise ValueError(
                f"Existing project has no files: {project_name}"
            )

        if (
            not isinstance(project_name, str)
            or not project_name
            or project_name != project_name.strip()
            or project_name in (".", "..")
            or "/" in project_name
            or "\\" in project_name
            or ":" in project_name
        ):
            raise ValueError(f"Invalid existing project name: {project_name!r}")

        project_path = (self.workspace.root / project_name).resolve()
        if project_path.parent != self.workspace.root or not project_path.is_dir():
            raise ValueError(f"Invalid existing project directory: {project_name}")

        docs_only = self._is_docs_only_update(task)

        if docs_only:
            allowed_paths = {"README.md"} if re.search(r"\breadme\b", task, re.I) else set()
            if not allowed_paths:
                allowed_paths = {
                    item for item in project_files
                    if item.lower().endswith((".md", ".rst", ".txt"))
                }
            # A documentation request may create README.md even if it does not exist.
            if re.search(r"\breadme\b", task, re.I):
                allowed_paths.add("README.md")
            instruction = (
                "DOCUMENTATION-ONLY UPDATE. Return only README.md content "
                "unless the task explicitly requests another documentation file. "
                "Never return or modify source code, configuration, or requirements."
            )
        else:
            allowed_paths = {
                item for item in project_files
                if re.search(r"(?<![\w])" + re.escape(item) + r"(?![\w])", task, re.I)
                or re.search(
                    r"(?<![\w])" + re.escape(item.rsplit("/", 1)[-1]) + r"(?![\w])",
                    task,
                    re.I,
                )
            }
            if not allowed_paths:
                raise ValueError(
                    "Existing-project update rejected: name the exact existing "
                    "source file you want to change."
                )
            instruction = (
                "Modify only the explicitly requested existing source file(s). "
                "Do not add files or change any other file."
            )

        inventory = "\\n".join(project_files)
        prompt = f"""
You are updating an existing project, not creating a new application.

Project name: {project_name}
User request: {task}

Existing project files:
{inventory}

{instruction}

Return only a JSON object with this structure:
{{
  "project_name": "{project_name}",
  "summary": "short summary of the update",
  "files": [
    {{"path": "README.md", "content": "complete file content"}}
  ]
}}

Rules:
- JSON only, no markdown fences or explanations.
- Return complete content for each file you intend to update.
- Use project-relative paths only.
- Do not return files outside the permitted scope.
"""

        self.set_status("thinking", {"task": task, "project_name": project_name})
        raw = await self.llm.generate(
            prompt=prompt,
            format="json",
            temperature=0.0,
            max_tokens=1800,
        )
        project = self._parse_project(raw)

        if project.get("project_name", "").strip() != project_name:
            raise ValueError("Update response changed the existing project name.")

        files = project.get("files")
        if not isinstance(files, list) or not files:
            raise ValueError("Update response must contain a non-empty files list.")

        validated = []
        seen = set()
        for item in files:
            if not isinstance(item, dict):
                raise ValueError("Every update file must be a JSON object.")

            relative_path = self._validate_update_relative_path(item.get("path"))
            content = item.get("content")
            if not isinstance(content, str):
                raise ValueError(f"Invalid content for update file: {relative_path}")
            if relative_path in seen:
                raise ValueError(f"Duplicate update file: {relative_path}")
            seen.add(relative_path)

            if relative_path not in allowed_paths:
                raise ValueError(
                    f"Update rejected: file is outside the permitted scope: "
                    f"{relative_path}"
                )

            full_relative_path = f"{project_name}/{relative_path}"
            if docs_only:
                if not relative_path.lower().endswith((".md", ".rst", ".txt")):
                    raise ValueError("Documentation updates may only write documentation files.")
            elif full_relative_path not in listed_files:
                raise ValueError(
                    f"Source update rejected: file does not already exist: "
                    f"{relative_path}"
                )

            validated.append({"path": relative_path, "content": content})

        # Validate Python syntax for every proposed source file before
        # writing any file, so a bad multi-file update cannot partially apply.
        for item in validated:
            relative_path = item["path"]
            if relative_path.lower().endswith((".py", ".pyw")):
                try:
                    ast.parse(item["content"], filename=relative_path)
                except SyntaxError as exc:
                    raise ValueError(
                        f"Invalid Python syntax in {relative_path}: {exc.msg}"
                    ) from exc

        # Validate the entire response before writing any files.
        for item in validated:
            full_path = f"{project_name}/{item['path']}"
            if full_path in listed_files:
                self.workspace.edit_file(full_path, item["content"])
            elif docs_only and item["path"] == "README.md":
                self.workspace.create_file(full_path, item["content"])
            else:
                raise ValueError(f"Refusing to create unapproved file: {item['path']}")

        if docs_only:
            execution = {
                "return_code": 0,
                "stdout": (
                    "Documentation update applied; execution skipped."
                ),
                "stderr": "",
                "skipped": True,
                "reason": "documentation_only",
            }
        else:
            execution = await asyncio.to_thread(self.run_project, project_name)

        result_status = (
            "success"
            if execution["return_code"] == 0
            else "failed"
        )

        # Include the current project files in the artifact snapshot,
        # including source files that this update did not modify.
        project_prefix = f"{project_name}/"
        inspected_files = self.inspect_project(project_name)
        artifact_files = [
            {
                "path": path[len(project_prefix):],
                "content": content,
            }
            for path, content in sorted(inspected_files.items())
            if path.startswith(project_prefix)
            and not path.endswith(".failed-generated-backup")
        ]

        result = {
            "project_name": project_name,
            "summary": project.get("summary", "Updated existing project"),
            "files": artifact_files,
            "workspace_path": project_name,
            "status": result_status,
            "execution": execution,
        }
        self.set_status(
            "idle" if result_status == "success" else "failed",
            {
                "task": task,
                "project_name": project_name,
                "workspace_path": project_name,
                "execution": execution,
            },
        )
        return json.dumps(result, indent=2, ensure_ascii=False)

    async def run(self, task: str) -> str:
        """
        Generate a complete project for the requested task.
        """

        self.set_status("thinking", {"task": task})

        print("\n===== CODER TASK =====")
        print(task)
        print("======================\n")

        prompt = self._build_prompt(task)

        print("\n===== CODER PROMPT LENGTH =====")
        print(f"Characters: {len(prompt)}")
        print("===============================\n")

        try:
            existing_update = self._find_existing_project_update(task)
            if existing_update is not None:
                project_name, _docs_only_hint = existing_update
                return await self._update_existing_project(task, project_name)

            # First attempt
            result = await self.llm.generate(
                prompt=prompt,
                format="json",
                temperature=0.1,
                max_tokens=3000,
            )

            try:
                print("\n===== RAW CODER OUTPUT =====")
                print(result)
                print("============================\n")
                project = self._parse_project(result)
            except Exception as first_error:
                # One controlled retry with an even stricter instruction.
                self.set_status(
                    "thinking",
                    {
                        "task": task,
                        "retry": True,
                        "reason": str(first_error),
                    },
                )

                retry_prompt = f"""
                Create the Python project requested below.

                Task:
                {task}

                Return ONLY one valid JSON object.

                Required structure:
                {{
                "project_name": "short_name",
                "summary": "short description",
                "files": [
                    {{
                    "path": "main.py",
                    "content": "complete file content"
                    }}
                ]
                }}

                Rules:
                - JSON only.
                - No markdown.
                - No explanations.
                - Use double quotes for JSON.
                - Escape quotes inside file content correctly.
                - Every file content must be complete.
                - Do not include absolute paths.
                - Do not use ../.
                - Keep the project as small as possible.
                """

                retry_result = await self.llm.generate(
                    prompt=retry_prompt,
                    format="json",
                    temperature=0.1,
                    max_tokens=3000,
                )

                project = self._parse_project(retry_result)

            try:
                self._ensure_known_requirements(project)
                self._remove_stdlib_requirements(project)
                self._validate_project(project)
                self._validate_flask_consistency(project)
                self._validate_flask_routes(project)

            except ValueError as validation_error:

                error_text = str(validation_error)

                # ==========================================================
                # PYTHON SYNTAX REPAIR
                # ==========================================================

                if error_text.startswith("Invalid Python syntax in "):

                    print("\nCODER: Generated Python contains a syntax error.")
                    print(f"Reason: {error_text}")
                    print("CODER: Asking LLM to repair the affected file...")

                    self.set_status(
                        "thinking",
                        {
                            "task": task,
                            "retry": True,
                            "reason": error_text,
                        },
                    )

                    # Extract the file path from:
                    # "Invalid Python syntax in main.py: ..."
                    prefix = "Invalid Python syntax in "
                    remaining = error_text[len(prefix):]

                    file_path, syntax_error = remaining.split(
                        ":",
                        1,
                    )

                    target_file = next(
                        (
                            file
                            for file in project["files"]
                            if file["path"] == file_path
                        ),
                        None,
                    )

                    if target_file is None:
                        raise ValueError(
                            f"Could not find generated file '{file_path}' "
                            "for syntax repair."
                        )

                    fixed_content = await self.fix_generated_file(
                        file_path=file_path,
                        content=target_file["content"],
                        syntax_error=syntax_error.strip(),
                    )

                    target_file["content"] = fixed_content

                    print("\n===== SYNTAX REPAIR RESULT =====")
                    print(fixed_content)
                    print("================================\n")

                    # Validate the repaired project again.
                    self._ensure_known_requirements(project)
                    self._remove_stdlib_requirements(project)
                    self._validate_project(project)
                    self._validate_flask_consistency(project)
                    self._validate_flask_routes(project)

                else:

                    # ======================================================
                    # EXISTING VALIDATION RETRY
                    # ======================================================

                    print("\nCODER: Project validation failed.")
                    print(f"Reason: {validation_error}")
                    print("CODER: Asking LLM to regenerate the project...")

                    self.set_status(
                        "thinking",
                        {
                            "task": task,
                            "retry": True,
                            "reason": str(validation_error),
                        },
                    )

                    validation_retry_prompt = f"""
            You are the Coder agent.

            Create the complete Python project requested below.

            USER REQUEST:
            {task}

            YOUR PREVIOUS PROJECT FAILED VALIDATION.

            VALIDATION ERROR:
            {validation_error}

            You must correct the problem described by the validation error.

            Return ONLY one valid JSON object.

            Required structure:

            {{
            "project_name": "short_name",
            "summary": "short description",
            "files": [
                {{
                "path": "main.py",
                "content": "complete file content"
                }}
            ]
            }}

            IMPORTANT RULES:

            - Return JSON only.
            - No markdown.
            - No explanations.
            - Every file must contain complete content.
            - Keep the project as one integrated application.
            - Do not create multiple independent projects.
            - Do not use absolute paths.
            - Do not use ../.
            - If Python code imports external packages, include a
            requirements.txt file containing all required packages.
            - Make sure requirements.txt matches the imports used by
            the generated Python files.
            - Do not omit required dependencies.
            - Do not use fake packages.
            - Do not use placeholder implementations.
            - The generated project must be runnable locally.
            - requirements.txt MUST contain EVERY external package
            imported by EVERY Python file.
            - Do NOT put Python standard-library modules such as
            json, datetime, os, sys, re, pathlib, or typing
            into requirements.txt.
            - Check every import before returning the project.
            - Make sure every Python file has valid syntax. - For Flask applications, ensure every HTML form field name matches the corresponding request.form field accessed by Python. - Ensure every template attribute such as task.description refers to a field actually defined on the corresponding model. - Ensure every form action uses an existing Flask route and the correct HTTP method. - Ensure buttons for completing or deleting records submit to implemented routes. - Ensure template variable names match the variables passed by render_template(). - Fix the specific validation error reported above, not just unrelated issues. - Do not add unnecessary packages.
            """

                    validation_retry_result = await self.llm.generate(
                        prompt=validation_retry_prompt,
                        format="json",
                        temperature=0.0,
                        max_tokens=3000,
                    )

                    print("\n===== VALIDATION RETRY OUTPUT =====")
                    print(validation_retry_result)
                    print("===================================\n")

                    project = self._parse_project(
                            validation_retry_result
                            )
                self._ensure_known_requirements(project)
                self._remove_stdlib_requirements(project)
                self._validate_project(project)
                self._validate_flask_consistency(project)
                self._validate_flask_routes(project)

            # Explicit existing-project updates return earlier through the
            # scoped update path. Normal generation must not overwrite projects.
            project_name = project["project_name"].strip()
            async with self._project_lock(project_name):
                unique_name = self._unique_project_name(project_name)
                if unique_name != project_name:
                    print(
                        f"CODER: '{project_name}' already exists; "
                        f"using '{unique_name}' instead."
                    )
                    project["project_name"] = unique_name
                    project_name = unique_name

                self._ensure_project_directory_available(project_name)
                workspace_path = self.write_project_to_workspace(project)

            # Run the generated application.
            execution_result = await asyncio.to_thread(self.run_project, workspace_path)

            # Attempt up to two repairs if execution fails.
            repair_attempts = 0
            while (
                execution_result["return_code"] != 0
                and repair_attempts < 2
            ):
                repair_attempts += 1
                print("\nCODER: Project failed. Asking LLM to fix it...")

                fix = await self.fix_project(
                    workspace_path,
                    execution_result,
                )

                file_path, fixed_content = self._validate_repair(
                    workspace_path,
                    fix,
                    task,
                )

                # Override an ineffective LLM suggestion only when the test
                # traceback and project AST prove a unique missing import.
                deterministic_fix = self._repair_missing_test_import(
                    workspace_path,
                    execution_result,
                )
                if deterministic_fix is not None:
                    file_path, fixed_content = deterministic_fix
                    self._validate_repair(
                        workspace_path,
                        {
                            "file": file_path,
                            "content": fixed_content,
                        },
                        task,
                    )

                self.edit_project_file(
                    workspace_path,
                    file_path,
                    fixed_content,
                )

                print("\nCODER: Repair applied. Running project again...")
                execution_result = await asyncio.to_thread(self.run_project, workspace_path)

            # Report the actual final execution result.
            print("\n" + "=" * 50)
            print("===== FINAL EXECUTION REPORT =====")
            print("=" * 50)

            print(f"Project: {project['project_name']}")
            print(f"Exit code: {execution_result.get('return_code')}")

            stdout = execution_result.get("stdout", "")
            stderr = execution_result.get("stderr", "")

            print("\n--- STDOUT ---")
            print(stdout if stdout else "(no output)")

            print("\n--- STDERR ---")
            print(stderr if stderr else "(no errors)")

            print("\n" + "=" * 50)
            # Report the actual outcome, including a failed repair.
            succeeded = execution_result["return_code"] == 0
            final_status = "idle" if succeeded else "failed"

            self.set_status(
                final_status,
                {
                    "task": task,
                    "project_name": project["project_name"],
                    "file_count": len(project["files"]),
                    "workspace_path": workspace_path,
                    "execution": execution_result,
                },
            )

            project["workspace_path"] = workspace_path
            project["execution"] = execution_result
            project["repair_attempts"] = repair_attempts
            project["status"] = "success" if succeeded else "failed"

            return json.dumps(
                project,
                indent=2,
                ensure_ascii=False,
            )

        except Exception as exc:
            self.set_status(
                "failed",
                {
                    "task": task,
                    "error": str(exc),
                },
            )

            raise

    def _build_prompt(self, task: str) -> str:

        """
    Build a compact project-generation prompt for the local 1.7B model.
    """
        return f"""
You are the Coder agent.

Your job is to BUILD ONE COMPLETE WORKING APPLICATION
that satisfies the user's request.

USER REQUEST:
{task}

IMPORTANT:

Treat the entire user request as ONE application.

All requested features must be implemented INSIDE THE SAME PROJECT.

DO NOT create separate projects for separate features.

DO NOT create example projects.

DO NOT create placeholder implementations.

DO NOT describe features that should be implemented later.

DO NOT say that a feature is missing or can be added later.

The application must implement the requested functionality now.

For example, if the user asks for:
- a website
- place recommendations
- weather-based recommendations
- itinerary-based recommendations
- food recommendations

then create ONE website containing ALL of those features.

The features must work together.

Return ONLY valid JSON in exactly this structure:

{{
  "project_name": "short_name",
  "summary": "short summary",
  "files": [
    {{
      "path": "main.py",
      "content": "complete source code"
    }}
  ]
}}

RULES:

- Create exactly ONE project.
- All requested functionality belongs to that project.
- Build the smallest complete implementation that satisfies the request.
- Include only necessary files.
- Write complete code.
- Never use TODO.
- Never use "...".
- Never use placeholders.
- Never leave requested features unimplemented.
- Never create multiple independent projects.
- Never create separate projects for different features.
- Integrate the features together.
- Use relative paths only.
- Do not use "../".
- Do not use absolute paths.
- Add requirements.txt when external packages are required.
- Keep the implementation simple enough to run locally.
- Do not include tests unless requested.
- Do not include README unless useful.
- Do not explain the code outside the JSON.
- Return ONLY the JSON object.
"""

    def _build_retry_prompt(
        self,
        task: str,
        previous_response: str,
        error: Exception,
    ) -> str:
        """
        Build a stricter retry prompt after malformed output.
        """

        return f"""
You are retrying a software project generation task.

Original request:

{task}

Your previous response could not be parsed as a valid project.

Parsing error:

{error}

Generate the project again.

CRITICAL:

Return ONLY valid JSON.

Use this exact structure:

{{
  "project_name": "short_project_name",
  "summary": "short description",
  "files": [
    {{
      "path": "main.py",
      "content": "complete file contents"
    }}
  ]
}}

The content fields contain source code.

Therefore JSON-escape all:

- double quotes
- backslashes
- newlines
- tabs
- control characters

Do not output Markdown.

Do not output ```json.

Do not output explanations.

Do not output comments outside the JSON object.

Every file must contain complete real content.

Include requirements.txt if external Python packages are needed.

Include README.md.

Do not use placeholders.

Do not use absolute paths.

Do not use ../.

The result MUST be a single valid JSON object.
"""

    def _parse_project(self, response: str) -> dict[str, Any]:
        """
        Parse the model response into a project dictionary.

        JSON mode should normally make this straightforward, but we
        still handle Markdown fences and surrounding whitespace.
        """

        if not response or not response.strip():
            raise ValueError("Coder returned an empty response")

        cleaned = response.strip()

        # Remove Markdown fences if a model still adds them.
        cleaned = re.sub(
            r"^```(?:json)?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = re.sub(
            r"\s*```$",
            "",
            cleaned,
        )

        cleaned = cleaned.strip()

        try:
            project = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Coder returned invalid JSON: "
                f"{exc}"
            ) from exc

        if not isinstance(project, dict):
            raise ValueError(
                "Coder response must be a JSON object"
            )

        return project
    def _ensure_known_requirements(
        self,
        project: dict[str, Any],
    ) -> bool:
        """
        Add requirements.txt for recognized third-party imports when absent.
        Existing requirements files are left untouched.
        Return True if a file was added.
        """
        files = project.get("files", [])

        if any(
            item.get("path", "").replace("\\\\", "/").lower()
            == "requirements.txt"
            for item in files
        ):
            return False

        imported_modules = set()

        for item in files:
            if item.get("path", "").lower().endswith(".py"):
                imported_modules.update(
                    self._get_python_imports(item.get("content", ""))
                )

        packages = sorted({
            PYTHON_PACKAGE_MAP[module]
            for module in imported_modules
            if module in PYTHON_PACKAGE_MAP
        })

        if not packages:
            return False

        files.append({
            "path": "requirements.txt",
            "content": "\n".join(packages) + "\n",
        })

        print(
            "CODER: Added requirements.txt for recognized imports: "
            + ", ".join(packages)
        )
        return True

    def _remove_stdlib_requirements(
        self,
        project: dict[str, Any],
    ) -> bool:
        """
        Remove Python standard-library modules accidentally listed
        in requirements.txt. Return True if anything was changed.
        """
        stdlib_names = {
            name.lower().replace("_", "-")
            for name in PYTHON_STDLIB_MODULES
        }

        changed = False

        for file_info in project.get("files", []):
            if file_info.get("path", "").lower() != "requirements.txt":
                continue

            kept_lines = []

            for line in file_info.get("content", "").splitlines():
                stripped = line.strip()

                if not stripped or stripped.startswith("#"):
                    kept_lines.append(line)
                    continue

                package_name = (
                    stripped.split("==")[0]
                    .split(">=")[0]
                    .split("<=")[0]
                    .split("~=")[0]
                    .split("!=")[0]
                    .strip()
                    .lower()
                    .replace("_", "-")
                )

                if package_name in stdlib_names:
                    print(
                        "CODER: Removing standard-library module "
                        f"from requirements.txt: {package_name}"
                    )
                    changed = True
                    continue

                kept_lines.append(line)

            file_info["content"] = "\n".join(kept_lines).strip()

            if file_info["content"]:
                file_info["content"] += "\n"

        return changed

    def _validate_project(self, project: dict[str, Any]) -> None:
        """
        Validate the project structure before it reaches ArtifactManager.
        """

        required_fields = [
            "project_name",
            "summary",
            "files",
        ]

        for field in required_fields:
            if field not in project:
                raise ValueError(
                    f"Coder project is missing '{field}'"
                )

        if not isinstance(project["project_name"], str):
            raise ValueError(
                "project_name must be a string"
            )

        if not project["project_name"].strip():
            raise ValueError(
                "project_name cannot be empty"
            )

        if not isinstance(project["summary"], str):
            raise ValueError(
                "summary must be a string"
            )

        files = project["files"]

        if not isinstance(files, list):
            raise ValueError(
                "files must be a list"
            )

        if not files:
            raise ValueError(
                "Coder generated no files"
            )

        for index, file_info in enumerate(files):
            if not isinstance(file_info, dict):
                raise ValueError(
                    f"File #{index + 1} must be an object"
                )

            if "path" not in file_info:
                raise ValueError(
                    f"File #{index + 1} is missing 'path'"
                )

            if "content" not in file_info:
                raise ValueError(
                    f"File #{index + 1} is missing 'content'"
                )

            path = file_info["path"]
            content = file_info["content"]

            if not isinstance(path, str):
                raise ValueError(
                    f"File #{index + 1} path must be a string"
                )

            if not isinstance(content, str):
                raise ValueError(
                    f"File #{index + 1} content must be a string"
                )

            if not path.strip():
                raise ValueError(
                    f"File #{index + 1} has an empty path"
                )

            # Security validation.
            if path.startswith("/"):
                raise ValueError(
                    f"Unsafe absolute path: {path}"
                )

            if path.startswith("\\"):
                raise ValueError(
                    f"Unsafe path: {path}"
                )

            normalized = path.replace("\\", "/")

            if ".." in normalized.split("/"):
                raise ValueError(
                    f"Unsafe traversal path: {path}"
                )

        # A software project should contain at least one useful source file.
        source_extensions = (
            ".py",
            ".js",
            ".ts",
            ".java",
            ".go",
            ".rs",
            ".sql",
        )

        has_source = any(
            file_info["path"].lower().endswith(source_extensions)
            for file_info in files
        )

        if not has_source:
            raise ValueError(
                "Coder project does not contain a source code file"
            )

                # Python projects using external packages should have requirements.
        python_files = any(
            file_info["path"].lower().endswith(".py")
            for file_info in files
        )

        if python_files:
            python_imports = set()

            for file_info in files:
                if file_info["path"].lower().endswith(".py"):
                    python_imports.update(
                        self._get_python_imports(
                            file_info["content"]
                        )
                    )

            external_packages = {
                PYTHON_PACKAGE_MAP[module]
                for module in python_imports
                if module in PYTHON_PACKAGE_MAP
            }

            has_requirements = any(
                file_info["path"].lower() == "requirements.txt"
                for file_info in files
            )

            if external_packages and not has_requirements:
                raise ValueError(
                    "Python project imports external packages "
                    f"{sorted(external_packages)} but has no "
                    "requirements.txt"
                )



        # README is expected for generated projects.
        has_readme = any(
            file_info["path"].lower() == "readme.md"
            for file_info in files
        )

        # Locate requirements.txt once for the entire project.
        requirements_file = next(
            (
                file_info
                for file_info in files
                if file_info["path"].lower() == "requirements.txt"
            ),
            None,
        )

        requirements = set()

        if requirements_file:
            for line in requirements_file["content"].splitlines():
                line = line.strip()

                if not line or line.startswith("#"):
                    continue

                # Extract a package name from common pip constraints.
                package_name = (
                    line.split("==")[0]
                    .split(">=")[0]
                    .split("<=")[0]
                    .split("~=")[0]
                    .split("!=")[0]
                    .strip()
                )

                normalized_package = (
                    package_name.lower().replace("_", "-")
                )

                if not normalized_package:
                    raise ValueError(
                        "requirements.txt contains an invalid package entry"
                    )

                # Reject standard-library modules listed as dependencies.
                if (
                    normalized_package.replace("-", "_")
                    in PYTHON_STDLIB_MODULES
                ):
                    raise ValueError(
                        "requirements.txt incorrectly contains Python "
                        f"standard-library module '{package_name}'"
                    )

                requirements.add(normalized_package)

        # Validate Python syntax and collect imports once per project.
        python_imports = set()

        for file_info in files:
            path = file_info["path"]
            content = file_info["content"]

            if not path.lower().endswith(".py"):
                continue

            try:
                ast.parse(content)
            except SyntaxError as exc:
                raise ValueError(
                    f"Invalid Python syntax in {path}: {exc}"
                ) from exc

            python_imports.update(
                self._get_python_imports(content)
            )

        # Ensure known third-party imports have declared dependencies.
        for module in python_imports:
            if module in PYTHON_STDLIB_MODULES:
                continue

            expected_package = PYTHON_PACKAGE_MAP.get(module)

            if expected_package and expected_package.lower().replace(
                "_", "-"
            ) not in requirements:
                raise ValueError(
                    "requirements.txt is missing "
                    f"package '{expected_package}' "
                    f"for Python import '{module}'"
                )

        # A project importing known third-party packages needs requirements.
        external_packages = {
            PYTHON_PACKAGE_MAP[module]
            for module in python_imports
            if module in PYTHON_PACKAGE_MAP
        }

        if external_packages and not requirements_file:
            raise ValueError(
                "Python project imports external packages "
                f"{sorted(external_packages)} but has no "
                "requirements.txt"
            )

    def _validate_flask_consistency(
        self,
        project: dict[str, Any],
    ) -> None:
        """
        Detect common mismatches between Flask templates and Python code.
        This is a targeted heuristic, not a complete HTML/Python analyzer.
        """
        files = project.get("files", [])

        python_sources = {
            file_info["path"]: file_info["content"]
            for file_info in files
            if file_info.get("path", "").lower().endswith(".py")
        }

        templates = {
            file_info["path"]: file_info["content"]
            for file_info in files
            if (
                file_info.get("path", "").lower().endswith((".html", ".htm"))
                or "/templates/" in (
                    "/" + file_info.get("path", "").lower()
                )
            )
        }

        all_python = "\n".join(python_sources.values())

        if "from flask import" not in all_python and "import flask" not in all_python:
            return

        # Collect fields explicitly accessed through request.form.
        import ast

        expected_form_fields = set()

        for source in python_sources.values():
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.Subscript):
                    continue

                value = node.value
                if (
                    isinstance(value, ast.Attribute)
                    and value.attr == "form"
                    and isinstance(value.value, ast.Name)
                    and value.value.id == "request"
                ):
                    key_node = node.slice
                    if isinstance(key_node, ast.Constant) and isinstance(
                        key_node.value, str
                    ):
                        expected_form_fields.add(key_node.value)

        template_fields = set()
        for template in templates.values():
            try:
                tree = ast.parse(
                    template,
                    mode="eval",
                )
                del tree
            except SyntaxError:
                pass

            # Match common HTML input, textarea and select names.
            import re

            for match in re.finditer(
                r"""(?:name)\s*=\s*["']([^"']+)["']""",
                template,
                flags=re.IGNORECASE,
            ):
                template_fields.add(match.group(1))

        # Only flag fields when the project has both templates and
        # explicit request.form field access.
        if templates and expected_form_fields and template_fields:
            missing_fields = expected_form_fields - template_fields
            if missing_fields:
                raise ValueError(
                    "Flask form/template mismatch: Python reads "
                    f"request.form fields {sorted(missing_fields)}, "
                    "but no matching named field was found in the HTML "
                    "templates. Make the form field names and backend "
                    "field names consistent."
                )

        # Detect simple task-model/template attribute mismatches.
        model_attributes = set()
        for source in python_sources.values():
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue

                if not any(
                    isinstance(base, ast.Attribute)
                    and base.attr == "Model"
                    for base in node.bases
                ):
                    continue

                for child in node.body:
                    if isinstance(child, ast.Assign):
                        for target in child.targets:
                            if isinstance(target, ast.Name):
                                model_attributes.add(target.id)
                    elif isinstance(child, ast.AnnAssign):
                        if isinstance(child.target, ast.Name):
                            model_attributes.add(child.target.id)

        if model_attributes and templates:
            for template in templates.values():
                for attribute in re.findall(
                    r"""{{\s*[\w.]+\.(\w+)\s*}}""",
                    template,
                ):
                    if (
                        attribute in {"id", "query", "all", "first"}
                        or attribute.startswith("_")
                    ):
                        continue

                    # Check only direct model-like attribute names.
                    if attribute not in model_attributes:
                        if (
                            "task." + attribute in template
                            and "class Task" in all_python
                        ):
                            raise ValueError(
                                "Flask template/model mismatch: template "
                                f"references 'task.{attribute}', but the "
                                "Task model does not declare that attribute. "
                                "Align the template with the model fields."
                            )


    def _validate_flask_routes(self, project) -> None:
        """Check simple, literal Flask form actions against declared routes."""
        import ast
        import re
        from urllib.parse import urlparse

        # Support project/file data represented as either dictionaries
        # or objects.
        if isinstance(project, dict):
            files = project.get("files", [])
        else:
            files = getattr(project, "files", [])

        python_sources = {}
        templates = {}

        for file in files:
            if isinstance(file, dict):
                path = file.get("path", "")
                content = file.get("content", "")
            else:
                path = getattr(file, "path", "")
                content = getattr(file, "content", "")

            if not isinstance(path, str) or not isinstance(content, str):
                continue

            normalized_path = path.replace("\\", "/").lower()

            if normalized_path.endswith(".py"):
                python_sources[path] = content
            elif normalized_path.endswith((".html", ".htm")):
                templates[path] = content

        all_python = "\n".join(python_sources.values())

        if not re.search(r"\bimport\s+flask\b|\bfrom\s+flask\b", all_python):
            return

        routes = {}

        # Collect literal routes from common Flask decorators.
        for source in python_sources.values():
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue

                for decorator in node.decorator_list:
                    if not isinstance(decorator, ast.Call):
                        continue

                    func = decorator.func
                    if not isinstance(func, ast.Attribute):
                        continue

                    if func.attr not in {"route", "get", "post", "put", "patch", "delete"}:
                        continue

                    if not isinstance(func.value, ast.Name):
                        continue

                    route_path = None
                    if decorator.args and isinstance(decorator.args[0], ast.Constant):
                        if isinstance(decorator.args[0].value, str):
                            route_path = decorator.args[0].value

                    if route_path is None:
                        continue

                    if func.attr == "route":
                        methods = {"GET", "HEAD", "OPTIONS"}
                        for keyword in decorator.keywords:
                            if keyword.arg == "methods" and isinstance(keyword.value, (ast.List, ast.Tuple, ast.Set)):
                                declared = {
                                    item.value.upper()
                                    for item in keyword.value.elts
                                    if isinstance(item, ast.Constant)
                                    and isinstance(item.value, str)
                                }
                                methods = declared | {"OPTIONS"}
                                if "GET" in methods:
                                    methods.add("HEAD")
                    else:
                        methods = {func.attr.upper(), "OPTIONS"}
                        if "GET" in methods:
                            methods.add("HEAD")

                    routes.setdefault(route_path.rstrip("/") or "/", set()).update(methods)

        if not routes or not templates:
            return

        # Skip uncertain cases such as url_for(), Jinja expressions,
        # external URLs, and actions with template variables.
        for template in templates.values():
            for form_match in re.finditer(
                r"<form\b([^>]*)>",
                template,
                flags=re.IGNORECASE | re.DOTALL,
            ):
                attributes = form_match.group(1)

                action_match = re.search(
                    r"""\baction\s*=\s*(['"])(.*?)\1""",
                    attributes,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                method_match = re.search(
                    r"""\bmethod\s*=\s*(['"])(.*?)\1""",
                    attributes,
                    flags=re.IGNORECASE,
                )

                # No action means the browser submits to the current URL.
                # Dynamic actions are deliberately left unchecked.
                if not action_match:
                    continue

                action = action_match.group(2).strip()
                if (
                    not action
                    or "{{" in action
                    or "{%" in action
                    or "url_for(" in action
                    or action.startswith("#")
                ):
                    continue

                parsed = urlparse(action)
                if parsed.scheme or parsed.netloc:
                    continue

                if "<" in action or ">" in action:
                    continue

                action_path = parsed.path.rstrip("/") or "/"
                method = (
                    method_match.group(2).strip().upper()
                    if method_match
                    else "GET"
                )

                if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                    continue

                if action_path in routes:
                    if method not in routes[action_path]:
                        raise ValueError(
                            "Flask form/route method mismatch: form action "
                            f"'{action_path}' uses {method}, but the route "
                            f"supports {sorted(routes[action_path])}. "
                            "Align the form method with the route."
                        )
                    continue

                # Avoid false positives when the app declares dynamic routes,
                # such as /delete/<int:item_id>.
                has_dynamic_routes = any(
                    "<" in route or ">" in route for route in routes
                )
                if not has_dynamic_routes:
                    raise ValueError(
                        "Flask form action mismatch: template submits to "
                        f"'{action_path}', but no matching literal Flask "
                        "route was found. Align the form action with a route."
                    )

    def _get_python_imports(self, content: str) -> set[str]:
        imports = set()

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return imports

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])

        return imports
