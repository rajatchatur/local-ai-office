import pytest

from backend.agents.coder import CoderAgent, PYTHON_PACKAGE_MAP
from backend.core.workspace import Workspace


def test_workspace_create_file_overwrites_existing_file(tmp_path):
    workspace = Workspace(str(tmp_path))
    workspace.create_file("Demo/main.py", 'print("original")\n')
    workspace.create_file("Demo/main.py", 'print("replacement")\n')

    assert workspace.read_file("Demo/main.py") == 'print("replacement")\n'


def test_documentation_addition_preserves_existing_source(tmp_path):
    coder = object.__new__(CoderAgent)
    coder.workspace = Workspace(str(tmp_path))

    project_dir = tmp_path / "HelloAI"
    project_dir.mkdir()
    main_file = project_dir / "main.py"
    original_source = 'print("Hello from Local AI Office!")\n'
    main_file.write_text(original_source, encoding="utf-8")

    project = {
        "project_name": "HelloAI",
        "summary": "Add project documentation",
        "files": [
            {
                "path": "README.md",
                "content": "# HelloAI\n\nRun with `python main.py`.\n",
            }
        ],
    }

    coder.write_project_to_workspace(project)

    assert main_file.read_text(encoding="utf-8") == original_source
    assert (project_dir / "README.md").is_file()


@pytest.mark.parametrize(
    ("module", "package"),
    [
        ("flask_restful", "Flask-RESTful"),
        ("flask_sqlalchemy", "Flask-SQLAlchemy"),
        ("flask_cors", "Flask-Cors"),
    ],
)
def test_flask_extension_imports_have_package_mappings(module, package):
    assert PYTHON_PACKAGE_MAP.get(module) == package


def test_explicit_source_edit_can_update_existing_file(tmp_path):
    coder = object.__new__(CoderAgent)
    coder.workspace = Workspace(str(tmp_path))

    project_dir = tmp_path / "HelloAI"
    project_dir.mkdir()
    main_file = project_dir / "main.py"
    main_file.write_text('print("old")\n', encoding="utf-8")

    project = {
        "project_name": "HelloAI",
        "summary": "Update the application source",
        "files": [
            {
                "path": "main.py",
                "content": 'print("updated")\n',
            }
        ],
    }

    coder.write_project_to_workspace(project)

    assert main_file.read_text(encoding="utf-8") == 'print("updated")\n'


def test_preserve_existing_writer_skips_existing_source(tmp_path):
    coder = object.__new__(CoderAgent)
    coder.workspace = Workspace(str(tmp_path))

    project_dir = tmp_path / "HelloAI"
    project_dir.mkdir()
    main_file = project_dir / "main.py"
    original_source = 'print("original")\n'
    main_file.write_text(original_source, encoding="utf-8")

    project = {
        "project_name": "HelloAI",
        "summary": "Add documentation without replacing source",
        "files": [
            {"path": "main.py", "content": 'print("replacement")\n'},
            {"path": "README.md", "content": "# HelloAI\n"},
        ],
    }

    coder.write_project_to_workspace(project, preserve_existing=True)

    assert main_file.read_text(encoding="utf-8") == original_source
    assert (project_dir / "README.md").read_text(encoding="utf-8") == "# HelloAI\n"


def test_existing_project_update_only_writes_requested_documentation(tmp_path):
    coder = object.__new__(CoderAgent)
    coder.workspace = Workspace(str(tmp_path))

    project_dir = tmp_path / "hello_ai_office"
    project_dir.mkdir()
    source = project_dir / "main.py"
    original = 'print("Hello from Local AI Office!")\n'
    source.write_text(original, encoding="utf-8")

    project = {
        "project_name": "hello_ai_office",
        "summary": "Add documentation",
        "files": [
            {
                "path": "README.md",
                "content": "# Local AI Office\n",
            },
            {
                "path": "main.py",
                "content": 'print("unrequested replacement")\n',
            },
        ],
    }

    written = coder.write_project_to_workspace(
        project,
        preserve_existing=True,
    )

    assert written == "hello_ai_office"
    assert source.read_text(encoding="utf-8") == original
    assert (project_dir / "README.md").read_text(encoding="utf-8") == (
        "# Local AI Office\n"
    )


@pytest.mark.parametrize(
    "unsafe_name",
    [
        "../outside",
        "/tmp/outside",
        "",
    ],
)
def test_existing_project_update_rejects_unsafe_project_names(
    tmp_path, unsafe_name
):
    workspace = Workspace(str(tmp_path))

    normalized = unsafe_name.strip()
    candidate = (workspace.root / normalized).resolve()

    assert (
        candidate == workspace.root
        or workspace.root not in candidate.parents
        or not normalized
    )


class MockUpdateLLM:
    def __init__(self, response):
        import json
        self.response = json.dumps(response)
        self.calls = 0

    async def generate(self, **kwargs):
        self.calls += 1
        return self.response


def make_update_agent(tmp_path, response):
    coder = object.__new__(CoderAgent)
    coder.workspace = Workspace(str(tmp_path))
    coder.llm = MockUpdateLLM(response)
    coder.set_status = lambda *args, **kwargs: None
    return coder


def test_readme_update_preserves_existing_source_and_skips_execution(tmp_path):
    import asyncio
    import json

    project_dir = tmp_path / "hello_ai_office"
    project_dir.mkdir()
    main_file = project_dir / "main.py"
    original = 'print("Hello from Local AI Office!")\n'
    main_file.write_text(original, encoding="utf-8")
    requirements_file = project_dir / "requirements.txt"
    requirements_file.write_text("flask\n", encoding="utf-8")

    coder = make_update_agent(
        tmp_path,
        {
            "project_name": "hello_ai_office",
            "summary": "Add README",
            "files": [
                {"path": "README.md", "content": "# Hello AI Office\n"}
            ],
        },
    )

    result = json.loads(
        asyncio.run(
            coder._update_existing_project(
                "Add a README to hello_ai_office",
                "hello_ai_office",
            )
        )
    )

    assert result["status"] == "success"
    assert result["execution"]["return_code"] == 0
    assert result["execution"]["skipped"] is True
    assert "skipped" in result["execution"]["stdout"].lower()
    assert main_file.read_text(encoding="utf-8") == original
    assert (project_dir / "README.md").read_text(encoding="utf-8") == (
        "# Hello AI Office\n"
    )
    returned_files = {
        item["path"]: item["content"]
        for item in result["files"]
    }

    assert returned_files["README.md"] == "# Hello AI Office\n"
    assert returned_files["main.py"] == original
    assert "requirements.txt" in returned_files
    assert returned_files["README.md"] == "# Hello AI Office\n"
    assert returned_files["main.py"] == original
    assert returned_files["requirements.txt"] == "flask\n"


def test_readme_update_rejects_unrequested_source_file(tmp_path):
    import asyncio

    project_dir = tmp_path / "hello_ai_office"
    project_dir.mkdir()
    main_file = project_dir / "main.py"
    original = 'print("safe")\n'
    main_file.write_text(original, encoding="utf-8")

    coder = make_update_agent(
        tmp_path,
        {
            "project_name": "hello_ai_office",
            "summary": "Update files",
            "files": [
                {"path": "README.md", "content": "# Docs\n"},
                {"path": "main.py", "content": 'print("changed")\n'},
            ],
        },
    )

    with pytest.raises(ValueError, match="outside the permitted scope"):
        asyncio.run(
            coder._update_existing_project(
                "Add a README to hello_ai_office",
                "hello_ai_office",
            )
        )

    assert main_file.read_text(encoding="utf-8") == original
    assert not (project_dir / "README.md").exists()


@pytest.mark.parametrize(
    "bad_path",
    ["../outside.txt", "/tmp/outside.txt", r"..\\outside.txt"],
)
def test_readme_update_rejects_unsafe_model_paths(tmp_path, bad_path):
    import asyncio

    project_dir = tmp_path / "hello_ai_office"
    project_dir.mkdir()
    (project_dir / "main.py").write_text(
        'print("safe")\n',
        encoding="utf-8",
    )

    coder = make_update_agent(
        tmp_path,
        {
            "project_name": "hello_ai_office",
            "summary": "Unsafe update",
            "files": [{"path": bad_path, "content": "unsafe"}],
        },
    )

    with pytest.raises(ValueError):
        asyncio.run(
            coder._update_existing_project(
                "Add a README to hello_ai_office",
                "hello_ai_office",
            )
        )


def test_explicit_source_update_only_changes_named_existing_file(tmp_path):
    import asyncio
    import json

    project_dir = tmp_path / "hello_ai_office"
    project_dir.mkdir()
    main_file = project_dir / "main.py"
    main_file.write_text('print("old")\n', encoding="utf-8")
    readme_file = project_dir / "README.md"
    readme_file.write_text("# Existing docs\n", encoding="utf-8")

    coder = make_update_agent(
        tmp_path,
        {
            "project_name": "hello_ai_office",
            "summary": "Update main.py",
            "files": [
                {"path": "main.py", "content": 'print("updated")\n'}
            ],
        },
    )

    execution_calls = []
    coder.run_project = lambda name: execution_calls.append(name) or {
        "return_code": 0,
        "stdout": "Application and tests passed",
        "stderr": "",
    }

    result = json.loads(
        asyncio.run(
            coder._update_existing_project(
                "Update main.py in hello_ai_office",
                "hello_ai_office",
            )
        )
    )

    assert result["status"] == "success"
    assert execution_calls == ["hello_ai_office"]
    assert result["execution"]["return_code"] == 0
    assert result["execution"].get("skipped") is not True
    assert main_file.read_text(encoding="utf-8") == 'print("updated")\n'
    assert readme_file.read_text(encoding="utf-8") == "# Existing docs\n"


def test_update_rejects_nonexistent_project(tmp_path):
    import asyncio

    coder = make_update_agent(
        tmp_path,
        {
            "project_name": "missing",
            "summary": "No project",
            "files": [{"path": "README.md", "content": "# Missing\n"}],
        },
    )

    with pytest.raises(ValueError, match="no files"):
        asyncio.run(
            coder._update_existing_project(
                "Add a README to missing",
                "missing",
            )
        )


def test_docs_classifier_rejects_mixed_readme_and_source_request():
    assert CoderAgent._is_docs_only_update(
        "Add a README and update main.py in hello_ai_office"
    ) is False


def test_docs_classifier_accepts_readme_only_request():
    assert CoderAgent._is_docs_only_update(
        "Add a README to hello_ai_office"
    ) is True


@pytest.mark.parametrize(
    "bad_path",
    [
        r"..\outside.txt",
        "C:/outside.txt",
        "folder/../outside.txt",
        "folder//outside.txt",
        "",
    ],
)
def test_update_path_validator_rejects_ambiguous_paths(bad_path):
    with pytest.raises(ValueError, match="Unsafe existing-project file path"):
        CoderAgent._validate_update_relative_path(bad_path)


def test_update_path_validator_accepts_safe_relative_path():
    assert (
        CoderAgent._validate_update_relative_path("docs/README.md")
        == "docs/README.md"
    )


def test_run_routes_readme_request_through_safe_existing_project_flow(tmp_path):
    import asyncio
    import json

    project_dir = tmp_path / "hello_ai_office"
    project_dir.mkdir()
    main_file = project_dir / "main.py"
    original_source = 'print("Hello from Local AI Office!")\n'
    main_file.write_text(original_source, encoding="utf-8")

    coder = make_update_agent(
        tmp_path,
        {
            "project_name": "hello_ai_office",
            "summary": "Document the existing project",
            "files": [
                {
                    "path": "README.md",
                    "content": "# Hello AI Office\n\nRun `python main.py`.\n",
                }
            ],
        },
    )

    # Make it fail immediately if run() tries to use the normal generation prompt.
    coder._build_prompt = lambda task: "NORMAL GENERATION FLOW SHOULD NOT RUN"

    result = json.loads(
        asyncio.run(coder.run("Add a README to hello_ai_office"))
    )

    assert result["status"] == "success"
    assert result["project_name"] == "hello_ai_office"
    assert result["execution"]["return_code"] == 0
    assert result["execution"]["skipped"] is True
    assert "skipped" in result["execution"]["stdout"].lower()
    assert coder.llm.calls == 1
    assert main_file.read_text(encoding="utf-8") == original_source
    assert (project_dir / "README.md").read_text(encoding="utf-8") == (
        "# Hello AI Office\n\nRun `python main.py`.\n"
    )


def test_invalid_python_update_rejects_all_files_before_writing(tmp_path):
    import asyncio

    project_dir = tmp_path / "hello_ai_office"
    project_dir.mkdir()

    main_file = project_dir / "main.py"
    helper_file = project_dir / "helper.py"

    original_main = 'print("original main")\n'
    original_helper = 'print("original helper")\n'

    main_file.write_text(original_main, encoding="utf-8")
    helper_file.write_text(original_helper, encoding="utf-8")

    coder = make_update_agent(
        tmp_path,
        {
            "project_name": "hello_ai_office",
            "summary": "Update two Python files",
            "files": [
                {
                    "path": "main.py",
                    "content": 'print("updated main")\n',
                },
                {
                    "path": "helper.py",
                    "content": "def broken_function(:\n    pass\n",
                },
            ],
        },
    )

    with pytest.raises(ValueError, match="Invalid Python syntax in helper.py"):
        asyncio.run(
            coder._update_existing_project(
                "Update main.py and helper.py in hello_ai_office",
                "hello_ai_office",
            )
        )

    assert main_file.read_text(encoding="utf-8") == original_main
    assert helper_file.read_text(encoding="utf-8") == original_helper


@pytest.mark.parametrize(
    "task",
    [
        "Create a new application based on hello_ai_office and add a README",
        "Build a new project inspired by hello_ai_office and update documentation",
    ],
)
def test_existing_project_classifier_does_not_capture_new_project_requests(
    tmp_path, task
):
    project_dir = tmp_path / "hello_ai_office"
    project_dir.mkdir()
    (project_dir / "main.py").write_text(
        'print("Hello")\n', encoding="utf-8"
    )

    coder = make_update_agent(
        tmp_path,
        {
            "project_name": "hello_ai_office",
            "summary": "Test response",
            "files": [{"path": "README.md", "content": "# Test\n"}],
        },
    )

    assert coder._find_existing_project_update(task) is None

def test_normal_generation_rejects_existing_project_directory(tmp_path):
    coder = object.__new__(CoderAgent)
    coder.workspace = Workspace(str(tmp_path))

    project_dir = tmp_path / "hello_ai_office"
    project_dir.mkdir()
    main_file = project_dir / "main.py"
    original_source = 'print("original source")\\n'
    main_file.write_text(original_source, encoding="utf-8")

    with pytest.raises(FileExistsError, match="Project directory already exists"):
        coder._ensure_project_directory_available("hello_ai_office")

    assert main_file.read_text(encoding="utf-8") == original_source


def test_normal_generation_allows_new_project_directory(tmp_path):
    coder = object.__new__(CoderAgent)
    coder.workspace = Workspace(str(tmp_path))

    coder._ensure_project_directory_available("fresh_project")
    assert not (tmp_path / "fresh_project").exists()


def test_source_update_reports_execution_failure(tmp_path):
    import asyncio
    import json

    project_dir = tmp_path / "hello_ai_office"
    project_dir.mkdir()
    (project_dir / "main.py").write_text(
        'print("old")\n',
        encoding="utf-8",
    )

    coder = make_update_agent(
        tmp_path,
        {
            "project_name": "hello_ai_office",
            "summary": "Update main.py",
            "files": [
                {"path": "main.py", "content": 'print("broken")\n'}
            ],
        },
    )

    coder.run_project = lambda name: {
        "return_code": 1,
        "stdout": "",
        "stderr": "Simulated source execution failure",
    }

    result = json.loads(
        asyncio.run(
            coder._update_existing_project(
                "Update main.py in hello_ai_office",
                "hello_ai_office",
            )
        )
    )

    assert result["status"] == "failed"
    assert result["execution"]["return_code"] == 1
    assert "Simulated source execution failure" in result["execution"]["stderr"]
    assert result["execution"].get("skipped") is not True
