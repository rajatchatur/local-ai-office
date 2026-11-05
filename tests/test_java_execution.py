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
def require_java():
    if not shutil.which("javac") or not shutil.which("java"):
        pytest.skip("Java compiler and runtime are required")


def test_java_hello_world_compiles_and_runs(tmp_path):
    agent = make_agent(
        tmp_path,
        "JavaHello",
        {
            "Main.java": (
                "public class Main {\n"
                "    public static void main(String[] args) {\n"
                '        System.out.println("Hello from Local AI Office");\n'
                "    }\n"
                "}\n"
            )
        },
    )

    result = agent.run_project("JavaHello")

    assert result["return_code"] == 0, result["stderr"]
    assert result["stdout"].strip() == "Hello from Local AI Office"


def test_java_compilation_error_returns_failure(tmp_path):
    agent = make_agent(
        tmp_path,
        "JavaCompileError",
        {
            "Main.java": (
                "public class Main {\n"
                "    public static void main(String[] args) {\n"
                '        System.out.println("missing quote);\n'
                "    }\n"
                "}\n"
            )
        },
    )

    result = agent.run_project("JavaCompileError")

    assert result["return_code"] != 0
    assert result["stderr"].strip()


def test_java_package_compiles_and_runs(tmp_path):
    agent = make_agent(
        tmp_path,
        "JavaPackage",
        {
            "src/Main.java": (
                "package demo;\n"
                "public class Main {\n"
                "    public static void main(String[] args) {\n"
                '        System.out.println("Package works");\n'
                "    }\n"
                "}\n"
            )
        },
    )

    result = agent.run_project("JavaPackage")

    assert result["return_code"] == 0, result["stderr"]
    assert result["stdout"].strip() == "Package works"


def test_java_timeout_returns_structured_failure(tmp_path):
    agent = make_agent(
        tmp_path,
        "JavaTimeout",
        {
            "Main.java": (
                "public class Main {\n"
                "    public static void main(String[] args) throws Exception {\n"
                "        Thread.sleep(10000);\n"
                "    }\n"
                "}\n"
            )
        },
    )

    original_run_command = agent.workspace.run_command

    def short_timeout(command, timeout=60, cwd=None, env=None):
        argv = command if isinstance(command, list) else command.split()

        if argv[:2] == ["java", "-cp"]:
            timeout = 2
        return original_run_command(
            command,
            timeout=timeout,
            cwd=cwd,
            env=env,
        )

    agent.workspace.run_command = short_timeout

    result = agent.run_project("JavaTimeout")

    assert result["return_code"] == 124
    assert "timed out" in result["stderr"].lower()
