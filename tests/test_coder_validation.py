import pytest

from backend.agents.coder import CoderAgent

def make_project(files):
    return {
        "project_name": "ValidationTest",
        "summary": "Test generated application validation",
        "files": [
            {"path": path, "content": content}
            for path, content in files.items()
        ],
    }

def make_coder():
    # These validator methods do not need the full agent or an LLM.
    return object.__new__(CoderAgent)

def test_flask_route_validator_rejects_unsupported_post_method():
    coder = make_coder()

    project = make_project({
        "app.py": (
            "from flask import Flask\n"
            "app = Flask(__name__)\n"
            "@app.route('/save', methods=['GET'])\n"
            "def save():\n"
            "    return 'ok'\n"
        ),
        "templates/index.html": (
            '<form action="/save" method="POST"></form>'
        ),
    })

    with pytest.raises(ValueError, match="POST"):
        coder._validate_flask_routes(project)

def test_flask_route_validator_accepts_matching_post_method():
    coder = make_coder()

    project = make_project({
        "app.py": (
            "from flask import Flask\n"
            "app = Flask(__name__)\n"
            "@app.route('/save', methods=['POST'])\n"
            "def save():\n"
            "    return 'ok'\n"
        ),
        "templates/index.html": (
            '<form action="/save" method="POST"></form>'
        ),
    })

    coder._validate_flask_routes(project)

def test_flask_route_validator_rejects_missing_literal_route():
    coder = make_coder()

    project = make_project({
        "app.py": (
            "from flask import Flask\n"
            "app = Flask(__name__)\n"
            "@app.route('/')\n"
            "def home():\n"
            "    return 'ok'\n"
        ),
        "templates/index.html": (
            '<form action="/missing" method="POST"></form>'
        ),
    })

    with pytest.raises(ValueError, match="matching literal Flask route"):
        coder._validate_flask_routes(project)
def test_removes_json_from_requirements_but_keeps_flask():
    coder = make_coder()

    project = make_project({
        "requirements.txt": "flask>=3.0\njson\nrequests==2.32.0\n",
    })

    changed = coder._remove_stdlib_requirements(project)

    assert changed is True

    requirements = project["files"][0]["content"]
    assert "json" not in requirements.splitlines()
    assert "flask>=3.0" in requirements
    assert "requests==2.32.0" in requirements


def test_stdlib_cleanup_reports_no_change_when_requirements_are_valid():
    coder = make_coder()

    project = make_project({
        "requirements.txt": "flask>=3.0\nrequests>=2.0\n",
    })

    changed = coder._remove_stdlib_requirements(project)

    assert changed is False
    assert "flask>=3.0" in project["files"][0]["content"]


def test_project_validator_rejects_missing_project_name():
    coder = make_coder()

    project = {
        "summary": "A test project",
        "files": [
            {"path": "main.py", "content": "print('hello')"},
        ],
    }

    with pytest.raises(ValueError, match="project_name"):
        coder._validate_project(project)
def test_flask_route_validator_skips_dynamic_url_for_action():
    coder = make_coder()

    project = make_project({
        "app.py": (
            "from flask import Flask, url_for\n"
            "app = Flask(__name__)\n"
            "@app.route('/save', methods=['POST'])\n"
            "def save():\n"
            "    return 'ok'\n"
        ),
        "templates/index.html": (
            '<form action="{{ url_for(\'save\') }}" '
            'method="POST"></form>'
        ),
    })

    # Dynamic Jinja actions are outside the static validator's scope.
    coder._validate_flask_routes(project)

def test_adds_requirements_for_known_external_imports():
    coder = make_coder()
    project = make_project({
        "main.py": (
            "from flask import Flask\n"
            "import requests\n"
            "app = Flask(__name__)\n"
        ),
    })

    changed = coder._ensure_known_requirements(project)

    assert changed is True
    requirements = next(
        item["content"]
        for item in project["files"]
        if item["path"] == "requirements.txt"
    )
    assert requirements.splitlines() == ["flask", "requests"]


def test_does_not_add_requirements_for_standard_library_only():
    coder = make_coder()
    project = make_project({
        "main.py": "import json\nimport sqlite3\nprint('hello')\n",
    })

    assert coder._ensure_known_requirements(project) is False
    assert all(
        item["path"] != "requirements.txt"
        for item in project["files"]
    )


def test_preserves_existing_requirements_file():
    coder = make_coder()
    project = make_project({
        "main.py": "from flask import Flask\n",
        "requirements.txt": "flask>=3.0\n",
    })

    assert coder._ensure_known_requirements(project) is False

    requirements = next(
        item["content"]
        for item in project["files"]
        if item["path"] == "requirements.txt"
    )
    assert requirements == "flask>=3.0\n"


def test_adds_requirements_for_known_external_imports():
    coder = make_coder()
    project = make_project({
        "main.py": (
            "from flask import Flask\n"
            "import requests\n"
            "app = Flask(__name__)\n"
        ),
    })

    changed = coder._ensure_known_requirements(project)

    assert changed is True
    requirements = next(
        item["content"]
        for item in project["files"]
        if item["path"] == "requirements.txt"
    )
    assert requirements.splitlines() == ["flask", "requests"]


def test_does_not_add_requirements_for_standard_library_only():
    coder = make_coder()
    project = make_project({
        "main.py": "import json\nimport sqlite3\nprint('hello')\n",
    })

    assert coder._ensure_known_requirements(project) is False
    assert all(
        item["path"] != "requirements.txt"
        for item in project["files"]
    )


def test_preserves_existing_requirements_file():
    coder = make_coder()
    project = make_project({
        "main.py": "from flask import Flask\n",
        "requirements.txt": "flask>=3.0\n",
    })

    assert coder._ensure_known_requirements(project) is False

    requirements = next(
        item["content"]
        for item in project["files"]
        if item["path"] == "requirements.txt"
    )
    assert requirements == "flask>=3.0\n"
