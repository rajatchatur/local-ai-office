import ast
import json
import re
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
    "pandas": "pandas",
    "numpy": "numpy",
    "boto3": "boto3",
    "snowflake": "snowflake-connector-python",
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

        self.llm = LlamaCppClient(
            model="qwen3-1.7b"
        )
        self.workspace = Workspace(
                "/Users/rajatchatur/Desktop/local-ai-office/workspace"
            )
    def write_project_to_workspace(self, project: dict) -> str:
        """
        Write a generated Project to the local workspace.
        """

        project_dir = project["project_name"].strip()

        for file in project["files"]:
            file_path = f"{project_dir}/{file['path']}"

            self.workspace.create_file(
                file_path,
                file["content"],
            )

        return project_dir


    def run_project(self, project_name: str) -> dict:
        """
        Install dependencies, validate Python syntax, and check
        whether the generated application can start.
        """
        project_files = self.inspect_project(project_name)
        print("DEBUG project_name:", repr(project_name))
        print("DEBUG project_files:", list(project_files.keys()))

        # 1. Install dependencies when requirements.txt exists.
        requirements_path = f"{project_name}/requirements.txt"

        if requirements_path in project_files:
            print("\nCODER: Installing project dependencies...")

            install_result = self.workspace.run_command(
                "python -m pip install -r requirements.txt",
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
            "python -m compileall -q .",
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

            import os
            import subprocess
            import sys

            try:
                result = subprocess.run(
                    [sys.executable, "-c", startup_script],
                    cwd=self.workspace._safe_path(project_name),
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
            except subprocess.TimeoutExpired as exc:
                stdout = exc.stdout or ""
                stderr = exc.stderr or ""

                if isinstance(stdout, bytes):
                    stdout = stdout.decode("utf-8", errors="replace")
                if isinstance(stderr, bytes):
                    stderr = stderr.decode("utf-8", errors="replace")

                return {
                    "return_code": 124,
                    "stdout": stdout,
                    "stderr": (
                        "Flask startup check timed out after 15 seconds."
                        + (f"\n{stderr}" if stderr else "")
                    ),
                }

            result = {
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

            if result["return_code"] == 0:
                print("CODER: Flask startup check passed.")
            else:
                print("CODER: Flask startup check failed.")

            return result



        # 5. For non-Flask projects, run the selected entry point.
        print("\nCODER: Running project...")

        return self.workspace.run_command(
            f"python {entry_point}",
            cwd=project_name,
            timeout=60,
        )



    def inspect_project(self, project_name: str) -> dict:
        """
        Read text files from a generated project.
        Skip binary and non-UTF-8 files safely.
        """
        files = self.workspace.list_files()

        project_files = [
            path
            for path in files
            if path.startswith(f"{project_name}/")
        ]

        result = {}

        for path in project_files:
            try:
                result[path] = self.workspace.read_file(path)
            except (UnicodeDecodeError, ValueError):
                print(
                    f"CODER: Skipping binary file: {path}"
                )
            except FileNotFoundError:
                print(
                    f"CODER: File disappeared during inspection: {path}"
                )

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

    Find the cause of the error.

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

        fix = json.loads(result)

        return fix
    async def repair_existing_project(
        self,
        project_name: str,
    ) -> dict:
        """
        Run an existing project, diagnose failures,
        apply an LLM-generated fix, and run it again.
        """

        print(f"\nCODER: Testing existing project '{project_name}'...")

        execution_result = self.run_project(project_name)

        if execution_result["return_code"] == 0:
            return {
                "project_name": project_name,
                "status": "success",
                "execution": execution_result,
            }

        print("\nCODER: Existing project failed.")
        print(execution_result)

        fix = await self.fix_project(
            project_name,
            execution_result,
        )

        print("\nCODER: LLM generated fix:")
        print(fix)

        file_path = fix["file"]

        prefix = f"{project_name}/"

        if file_path.startswith(prefix):
            file_path = file_path[len(prefix):]

        self.edit_project_file(
            project_name,
            file_path,
            fix["content"],
        )

        print("\nCODER: Fix applied.")
        print("CODER: Running project again...")

        execution_result = self.run_project(project_name)

        return {
            "project_name": project_name,
            "status": (
                "success"
                if execution_result["return_code"] == 0
                else "failed"
            ),
            "fix": fix,
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
            # First attempt
            result = await self.llm.generate(
                prompt=prompt,
                format="json",
                temperature=0.1,
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
                    max_tokens=1200,
                )

                project = self._parse_project(retry_result)

            try:
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
                        max_tokens=1200,
                    )

                    print("\n===== VALIDATION RETRY OUTPUT =====")
                    print(validation_retry_result)
                    print("===================================\n")

                    project = self._parse_project(
                            validation_retry_result
                            )
                self._remove_stdlib_requirements(project)
                self._validate_project(project)
                self._validate_flask_consistency(project)
                self._validate_flask_routes(project)
            
            workspace_path = self.write_project_to_workspace(project)

            # Run the generated application.
            execution_result = self.run_project(workspace_path)

            # Attempt once repair if execution fails.
            if execution_result["return_code"] != 0:
                print("\nCODER: Project failed. Asking LLM to fix it...")

                fix = await self.fix_project(
                    workspace_path,
                    execution_result,
                )

                if not isinstance(fix, dict):
                    raise ValueError("LLM repair response must be a JSON object.")

                file_path = fix.get("file")
                fixed_content = fix.get("content")

                if not isinstance(file_path, str) or not isinstance(
                    fixed_content, str
                ):
                    raise ValueError(
                        "LLM repair must contain string fields 'file' and 'content'."
                    )

                # Accept either a project-relative path or a path
                # prefixed with the project directory.
                prefix = f"{workspace_path}/"
                if file_path.startswith(prefix):
                    file_path = file_path[len(prefix):]

                normalized_path = file_path.replace("\\", "/")

                if (
                    not normalized_path
                    or normalized_path.startswith("/")
                    or "\\" in file_path
                    or ".." in normalized_path.split("/")
                ):
                    raise ValueError(
                        f"LLM returned an unsafe repair path: {file_path}"
                    )

                # Only allow edits to files already in this project.
                existing_files = self.inspect_project(workspace_path)
                allowed_paths = {
                    path[len(prefix):]
                    for path in existing_files
                    if path.startswith(prefix)
                }

                if normalized_path not in allowed_paths:
                    raise ValueError(
                        f"LLM repair targeted a file outside the project "
                        f"or a file that does not exist: {file_path}"
                    )

                # Validate repaired Python syntax before writing it.
                if normalized_path.endswith(".py"):
                    try:
                        ast.parse(fixed_content)
                    except SyntaxError as exc:
                        raise ValueError(
                            f"LLM repair still contains invalid Python syntax: {exc}"
                        ) from exc

                self.edit_project_file(
                    workspace_path,
                    normalized_path,
                    fixed_content,
                )

                print("\nCODER: Repair applied. Running project again...")
                execution_result = self.run_project(workspace_path)

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